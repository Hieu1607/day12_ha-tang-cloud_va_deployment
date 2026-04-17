"""
Economics AI Chatbot — Production-ready FastAPI + Gradio

Features:
  - Groq LLM (llama-3.3-70b-versatile) with economics-only system prompt
  - API key authentication on /ask
  - Sliding-window rate limiting (10 req/min)
  - Monthly cost guard ($10/user/month)
  - Health + readiness probes
  - Graceful shutdown via lifespan
  - Structured JSON logging
  - Gradio UI mounted at /ui (server-side, key never exposed to browser)
"""
import json
import logging
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import gradio as gr
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_usage
from app.llm import chat
from app.rate_limiter import check_rate_limit

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── State ─────────────────────────────────────────────────
START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0


# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _is_ready
    logger.info(json.dumps({"event": "startup", "app": settings.app_name, "env": settings.environment}))
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))


# ── App ───────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        duration_ms = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration_ms,
        }))
        return response
    except Exception:
        _error_count += 1
        raise


# ── Pydantic models ───────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field(default="default", max_length=64)


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str


# ── REST endpoints ────────────────────────────────────────
@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "ui": "/ui",
        "health": "/health",
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    api_key: str = Depends(verify_api_key),
):
    """Send a question to the economics AI. Requires X-API-Key header."""
    check_rate_limit(api_key[:16])
    check_budget(body.user_id)

    logger.info(json.dumps({"event": "ask", "user": body.user_id, "q_len": len(body.question)}))

    answer, input_tokens, output_tokens = chat(body.question)
    record_usage(body.user_id, input_tokens, output_tokens)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe — platform restarts container if this fails."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe — load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Not ready")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
    }


# ── Gradio UI ─────────────────────────────────────────────
def _gradio_chat(message: str, history: list[list[str]]) -> str:
    """Server-side Gradio handler — calls LLM directly, key never leaves server."""
    if not message.strip():
        return "Please enter a question."

    # Convert Gradio [[user, bot], ...] format to message list
    prior: list[dict] = []
    for user_msg, bot_msg in history:
        prior.append({"role": "user", "content": user_msg})
        prior.append({"role": "assistant", "content": bot_msg})

    try:
        check_rate_limit("gradio-ui")
    except HTTPException:
        return "Rate limit reached. Please wait a minute before sending more messages."

    try:
        check_budget("gradio-ui")
    except HTTPException:
        return "Monthly budget limit reached. The service will reset next month."

    answer, input_tokens, output_tokens = chat(message, prior)
    record_usage("gradio-ui", input_tokens, output_tokens)
    return answer


_gradio_app = gr.ChatInterface(
    fn=_gradio_chat,
    title="Economics AI Chatbot",
    description=(
        "Ask me anything about economics — micro/macroeconomics, markets, "
        "monetary policy, trade, GDP, inflation, and more."
    ),
    examples=[
        "What is the difference between monetary and fiscal policy?",
        "Explain supply and demand with a real-world example.",
        "What causes inflation and how is it controlled?",
        "What is GDP and why does it matter?",
    ],
    theme=gr.themes.Soft(),
)

# Mount Gradio at /ui — this returns the wrapped ASGI app
app = gr.mount_gradio_app(app, _gradio_app, path="/ui")


# ── Graceful shutdown ─────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal_received", "signum": signum}))


signal.signal(signal.SIGTERM, _handle_signal)


# ── Entry point ───────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
