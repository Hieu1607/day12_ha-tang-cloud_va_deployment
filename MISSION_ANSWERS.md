# MISSION ANSWERS

> **Student Name:** Nguyễn Minh Hiếu
> **Student ID:** 2A202600401 
> **Date:** 18/04/2026

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns trong `01-localhost-vs-production/develop/app.py`

Ít nhất 5 vấn đề tìm được:

1. Hardcoded secrets trong code:
	 - `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`
	 - `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`
2. Không có config management theo environment variables (`DEBUG`, `MAX_TOKENS`, port đều hardcode).
3. Dùng `print()` để log thay vì structured logging.
4. Log lộ secret (`print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`).
5. Không có health check endpoint (`/health`) để platform kiểm tra liveness.
6. Host bind vào `localhost` nên không truy cập được từ ngoài container/cloud.
7. Port cố định `8000`, không đọc từ env var `PORT` (Railway/Render/Cloud Run thường inject).
8. `reload=True` (debug reload) bật ở runtime, không phù hợp production.

### Exercise 1.3: So sánh `develop/app.py` và `production/app.py`

| Feature | Basic (develop) | Advanced (production) | Tại sao quan trọng? |
|---|---|---|---|
| Config | Hardcode trực tiếp trong code | Đọc từ `settings` (environment variables) | Giúp deploy nhiều môi trường (dev/staging/prod) không sửa code, tránh lộ secrets |
| Health check | Không có | Có `/health` (liveness) và `/ready` (readiness) | Orchestrator/load balancer biết khi nào restart instance hoặc route traffic |
| Logging | `print()` dạng text, có log secret | Structured JSON logging bằng `logging`, không log secrets | Dễ truy vấn tập trung, giám sát tốt hơn, an toàn hơn |
| Shutdown | Đột ngột, không lifecycle rõ ràng | Có `lifespan` startup/shutdown + xử lý `SIGTERM` | Hoàn tất in-flight requests và cleanup trước khi tắt, giảm lỗi mất request |

Điểm khác biệt bổ sung:

- Binding:
	- Basic: `host="localhost"`
	- Advanced: `host=settings.host` (thường là `0.0.0.0`)
	- Ý nghĩa: Chạy được trong container và nhận traffic từ bên ngoài.
- Port:
	- Basic: `port=8000` cố định
	- Advanced: `port=settings.port`
	- Ý nghĩa: Tương thích cloud platform inject cổng runtime.
- Validation input:
	- Basic: Không validate request body chuẩn JSON.
	- Advanced: Kiểm tra `question`, trả về `422` nếu thiếu.
	- Ý nghĩa: API behavior rõ ràng, tránh crash do input lỗi.

### Checkpoint 1

- [x] Hiểu tại sao hardcode secrets là nguy hiểm
- [x] Biết cách dùng environment variables
- [x] Hiểu vai trò của health check endpoint
- [x] Biết graceful shutdown là gì

## Part 2: Docker Containerization

### Exercise 2.1: Đọc `02-docker/develop/Dockerfile`

1. Base image là gì?
	 - `python:3.11`

2. Working directory là gì?
	 - `WORKDIR /app`

3. Tại sao `COPY requirements.txt` trước?
	 - Để tận dụng Docker layer cache.
	 - Nếu code thay đổi nhưng dependencies không đổi, Docker không cần cài lại toàn bộ package, build nhanh hơn nhiều.

4. `CMD` vs `ENTRYPOINT` khác nhau thế nào?
	 - `CMD`: lệnh mặc định, dễ bị override khi chạy `docker run <image> <command khác>`.
	 - `ENTRYPOINT`: định nghĩa executable chính của container, thường khó bị thay thế hoàn toàn hơn.
	 - Trong file hiện tại dùng `CMD ["python", "app.py"]` vì đơn giản và linh hoạt cho môi trường học.

### Exercise 2.3: Multi-stage build trong `02-docker/production/Dockerfile`

- Stage 1 (`builder`) làm gì?
	- Dùng `python:3.11-slim`.
	- Cài build tools (`gcc`, `libpq-dev`).
	- Cài dependencies vào `/root/.local` bằng `pip install --user`.

- Stage 2 (`runtime`) làm gì?
	- Dùng image sạch `python:3.11-slim`.
	- Tạo non-root user `appuser`.
	- Chỉ copy packages cần chạy từ stage builder + source code app.
	- Cấu hình `PATH`, `PYTHONPATH`, `HEALTHCHECK`, rồi chạy uvicorn.

- Tại sao image nhỏ hơn?
	- Không mang theo toàn bộ build dependencies/toolchain của giai đoạn build.
	- Runtime chỉ chứa phần cần thiết để chạy ứng dụng.
	- Giảm kích thước image và giảm attack surface.

So sánh kích thước (mang tính tham chiếu từ lab):
- Single-stage thường lớn hơn đáng kể (có thể ~700MB đến ~1GB tùy deps).
- Multi-stage slim thường nhỏ hơn nhiều (thường khoảng ~150MB đến ~400MB tùy deps).

### Exercise 2.4: Phân tích `docker-compose.yml` và architecture

Services được start:
1. `agent`: FastAPI AI agent.
2. `redis`: cache/session/rate limiting store.
3. `qdrant`: vector database cho RAG/search.
4. `nginx`: reverse proxy + load balancer public-facing.

Cách các service communicate:
- Client chỉ gọi vào `nginx` qua port `80` (và `443` nếu có cert).
- `nginx` proxy request vào upstream `agent_backend` (`agent:8000`).
- `agent` gọi nội bộ qua network `internal` đến:
	- `redis:6379`
	- `qdrant:6333`
- `depends_on` + `healthcheck` đảm bảo thứ tự sẵn sàng cơ bản trước khi nhận traffic.

Architecture tóm tắt:
- `Client -> Nginx -> Agent`
- `Agent -> Redis`
- `Agent -> Qdrant`

Ý nghĩa production:
- Nginx đứng trước để routing, rate limiting cơ bản và security headers.
- Agent không expose trực tiếp ra ngoài internet trong compose này.
- Dễ scale theo chiều ngang ở tầng agent.

### Checkpoint 2

- [x] Hiểu cấu trúc Dockerfile
- [x] Biết lợi ích của multi-stage builds
- [x] Hiểu Docker Compose orchestration
- [x] Biết cách debug container (`docker logs`, `docker exec`)

---

## Part 3: Cloud Deployment

### Exercise 3.1: Deploy Railway

**Public URL:** https://glorious-tranquility-production-7cd7.up.railway.app/

**Screenshot:** xem `image.png` trong repo — browser truy cập root URL trả về:
```json
{"message":"AI Agent running on Railway!","docs":"/docs","health":"/health"}
```

**Steps thực hiện:**
1. Cài Railway CLI: `npm i -g @railway/cli`
2. Đăng nhập: `railway login`
3. Khởi tạo project: `railway init`
4. Set environment variables:
   ```bash
   railway variables set PORT=8000
   railway variables set AGENT_API_KEY=my-secret-key
   ```
5. Deploy: `railway up`
6. Lấy domain: `railway domain` → `https://glorious-tranquility-production-7cd7.up.railway.app`

**Test kết quả:**
```bash
# Root endpoint
curl https://glorious-tranquility-production-7cd7.up.railway.app/
# {"message":"AI Agent running on Railway!","docs":"/docs","health":"/health"}

# Health check
curl https://glorious-tranquility-production-7cd7.up.railway.app/health
# {"status":"ok"}

# Agent endpoint (với API key)
curl https://glorious-tranquility-production-7cd7.up.railway.app/ask \
  -X POST \
  -H "X-API-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### Exercise 3.2: So sánh `render.yaml` vs `railway.toml`

| Điểm so sánh | `railway.toml` | `render.yaml` |
|---|---|---|
| Format | TOML | YAML |
| Build system | Nixpacks (auto-detect) hoặc Dockerfile | Chỉ định rõ `buildCommand` |
| Health check | `healthcheckPath` + `healthcheckTimeout` | `healthCheckPath` |
| Restart policy | `restartPolicyType = "ON_FAILURE"` (tường minh) | Render tự xử lý, không cần khai báo |
| Secrets | Set qua CLI `railway variables set` hoặc Dashboard | `sync: false` (set tay trên Dashboard) hoặc `generateValue: true` |
| Redis | Không khai báo trong toml, add riêng trên Dashboard | Khai báo service `type: redis` ngay trong file |
| Region | Không có trong toml cơ bản | Có `region: singapore` |
| Auto-deploy | Mặc định khi push | `autoDeploy: true` tường minh |

**Nhận xét:** Railway ưu tiên CLI-driven workflow với cấu hình tối giản; Render ưu tiên Infrastructure-as-Code khai báo toàn bộ stack (app + Redis) trong 1 file.

### Checkpoint 3

- [x] Deploy thành công lên Railway
- [x] Có public URL hoạt động: https://glorious-tranquility-production-7cd7.up.railway.app/
- [x] Hiểu cách set environment variables trên cloud
- [x] Biết cách xem logs (`railway logs`)

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication — phân tích `04-api-gateway/develop/app.py`

**API key được check ở đâu?**
Trong dependency function `verify_api_key` (dòng 39–54), được inject vào endpoint `/ask` qua `Depends(verify_api_key)`. FastAPI tự động gọi dependency này trước khi xử lý request.

**Điều gì xảy ra nếu sai key?**
- Không gửi header → `401 Unauthorized` với message `"Missing API key. Include header: X-API-Key: <your-key>"`
- Gửi sai key → `403 Forbidden` với message `"Invalid API key."`

**Làm sao rotate key?**
Chỉ cần update env var `AGENT_API_KEY` và restart service — không cần sửa code. Trong production nên dùng secret manager (AWS Secrets Manager, Railway Variables) để rotate mà không cần redeploy.

**Test kết quả:**
```bash
# Không có key → 401
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# Có key đúng → 200
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: demo-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# {"question":"Hello","answer":"..."}
```

### Exercise 4.2: JWT Authentication — phân tích `04-api-gateway/production/auth.py`

**JWT Flow:**
1. Client `POST /auth/token` với `username` + `password`
2. Server kiểm tra credentials trong `DEMO_USERS`, gọi `create_token()` → tạo JWT payload gồm `sub` (username), `role`, `iat`, `exp` → ký bằng `SECRET_KEY` với `HS256`
3. Client nhận token, gửi mọi request tiếp theo với header `Authorization: Bearer <token>`
4. Server gọi `verify_token()` → decode và verify signature + expiry → extract `username` và `role` → xử lý request

**Test lấy token và gọi API:**
```bash
# Bước 1: Lấy token
curl http://localhost:8000/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'
# {"access_token":"eyJ...","token_type":"bearer"}

# Bước 2: Dùng token
TOKEN="eyJ..."
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
# {"question":"Explain JWT","answer":"..."}
```

**Ưu điểm JWT so với API key đơn giản:**
- Stateless — server không cần lưu session, chỉ verify signature
- Có expiry tự động (60 phút) → giảm rủi ro nếu token bị lộ
- Chứa thông tin user (`role`) → authorization logic không cần query DB thêm

### Exercise 4.3: Rate Limiting — phân tích `04-api-gateway/production/rate_limiter.py`

**Algorithm được dùng:** Sliding Window Counter
- Mỗi user có một `deque` lưu timestamps của các request trong window 60 giây
- Mỗi request: loại bỏ timestamps cũ (ngoài window), đếm số còn lại, so sánh với `max_requests`
- Ưu điểm so với Fixed Window: không bị burst kép ở ranh giới window

**Limit:**
- User thường: `10 req/phút` (instance `rate_limiter_user`)
- Admin: `100 req/phút` (instance `rate_limiter_admin`)

**Bypass limit cho admin:**
Dùng instance `rate_limiter_admin` riêng cho user có `role == "admin"` (inject qua JWT claim `role`).

**Test rate limit:**
```bash
TOKEN="<jwt_token>"
for i in {1..15}; do
  curl http://localhost:8000/ask -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"Test $i\"}"
  echo ""
done
# Request thứ 11 trở đi → 429 Too Many Requests
# {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":...}}
# Headers: X-RateLimit-Limit: 10, X-RateLimit-Remaining: 0, Retry-After: <seconds>
```

### Exercise 4.4: Cost Guard — Implementation

**Approach được implement trong `04-api-gateway/production/cost_guard.py`:**

```python
import redis
from datetime import datetime

r = redis.Redis()

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"

    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:
        return False

    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)  # 32 ngày
    return True
```

**Giải thích logic:**
- Key Redis theo dạng `budget:<user_id>:<YYYY-MM>` → tự động "reset" sang tháng mới khi tháng đổi
- `incrbyfloat` là atomic → an toàn khi nhiều instances chạy đồng thời (không race condition)
- TTL 32 ngày để key tự xóa sau khi không còn dùng, không cần cron job cleanup
- `check_budget()` gọi trước khi invoke LLM; `record_usage()` gọi sau khi LLM trả về để ghi token thực tế

**Trong production code `CostGuard` class:**
- Check cả per-user daily budget ($1/ngày) và global daily budget ($10/ngày)
- Log warning khi user đạt 80% budget
- Trả về `402 Payment Required` khi vượt user budget
- Trả về `503 Service Unavailable` khi vượt global budget

### Checkpoint 4

- [x] Implement API key authentication
- [x] Hiểu JWT flow
- [x] Implement rate limiting
- [x] Implement cost guard với Redis

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Checks — phân tích `05-scaling-reliability/develop/app.py`

**Implementation:**

```python
@app.get("/health")
def health():
    """Liveness probe — container còn sống không?"""
    uptime = round(time.time() - START_TIME, 1)
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/ready")
def ready():
    """Readiness probe — sẵn sàng nhận traffic không?"""
    if not _is_ready:
        raise HTTPException(
            status_code=503,
            detail="Agent not ready. Check back in a few seconds.",
        )
    return {"ready": True, "in_flight_requests": _in_flight_requests}
```

**Sự khác biệt liveness vs readiness:**
| | `/health` (Liveness) | `/ready` (Readiness) |
|---|---|---|
| Mục đích | "Process còn sống không?" | "Sẵn sàng nhận request chưa?" |
| Khi fail | Platform **restart** container | Load balancer **ngừng route** traffic vào instance |
| Fail khi nào | Deadlock, crash, memory 100% | Đang khởi động, Redis down, đang shutdown |
| Luôn trả 200? | Gần như vậy (chỉ fail nếu process thực sự hỏng) | Không — trả 503 trong startup/shutdown |

### Exercise 5.2: Graceful Shutdown — phân tích

**Implementation trong `05-scaling-reliability/develop/app.py`:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    # Startup
    _is_ready = True
    logger.info("Agent is ready!")
    yield
    # Shutdown — phần này chạy khi nhận SIGTERM
    _is_ready = False
    logger.info("Graceful shutdown initiated...")
    timeout = 30
    elapsed = 0
    while _in_flight_requests > 0 and elapsed < timeout:
        logger.info(f"Waiting for {_in_flight_requests} in-flight requests...")
        time.sleep(1)
        elapsed += 1
    logger.info("Shutdown complete")

def handle_sigterm(signum, frame):
    logger.info(f"Received signal {signum} — uvicorn will handle graceful shutdown")

signal.signal(signal.SIGTERM, handle_sigterm)
```

**Luồng graceful shutdown:**
1. Orchestrator (K8s/Railway/Docker) gửi `SIGTERM` → uvicorn bắt tín hiệu
2. `_is_ready = False` → `/ready` trả 503 → load balancer ngừng route traffic mới vào
3. Vòng lặp chờ `_in_flight_requests == 0` (tối đa 30 giây)
4. Sau khi tất cả request hoàn thành, process exit cleanly
5. Nếu quá 30 giây → orchestrator gửi `SIGKILL` (force kill)

**Test:**
```bash
python app.py &
PID=$!
# Gửi request chậm
curl http://localhost:8000/ask -X POST \
  -d '{"question": "Long task"}' &
# Ngay lập tức kill
kill -TERM $PID
# Quan sát log: agent chờ request hoàn thành trước khi exit
```

### Exercise 5.3: Stateless Design — phân tích `05-scaling-reliability/production/app.py`

**Anti-pattern (stateful):**
```python
conversation_history = {}  # in-memory — mất khi restart, không share giữa instances

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])  # instance-local state
```

**Production (stateless với Redis):**
```python
# Trong production/app.py — lưu session vào Redis với TTL
def save_session(session_id: str, data: dict, ttl_seconds: int = 3600):
    serialized = json.dumps(data)
    _redis.setex(f"session:{session_id}", ttl_seconds, serialized)

def load_session(session_id: str) -> dict:
    data = _redis.get(f"session:{session_id}")
    return json.loads(data) if data else {}
```

**Tại sao stateless quan trọng khi scale:**
- Instance 1 nhận request 1 của User A → lưu history trong memory của Instance 1
- Instance 2 nhận request 2 của User A → KHÔNG có history → agent mất context → bug
- Với Redis: tất cả instances đều đọc/ghi chung 1 store → bất kỳ instance nào cũng serve đúng

Response còn trả về `"served_by": INSTANCE_ID` để chứng minh các request có thể được serve bởi các instances khác nhau mà conversation vẫn liên tục.

### Exercise 5.4: Load Balancing

**Chạy với Nginx:**
```bash
docker compose up --scale agent=3
```

Docker Compose khởi động 3 instances của `agent` (agent_1, agent_2, agent_3) và Nginx phân tán traffic theo thuật toán round-robin.

**Cấu hình Nginx upstream:**
```nginx
upstream agent_backend {
    server agent:8000;  # Docker DNS resolve ra tất cả containers có tên "agent"
}
```

**Quan sát:**
```bash
# Gọi 10 requests
for i in {1..10}; do
  curl http://localhost/ask -X POST \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"Request $i\"}"
done

# Check logs — thấy requests phân tán qua 3 instances
docker compose logs agent | grep "served_by"
# agent_1 | served_by: instance-abc123
# agent_2 | served_by: instance-def456
# agent_3 | served_by: instance-ghi789
```

**Nếu 1 instance die:** Nginx health check phát hiện, tự động bỏ instance đó khỏi pool, traffic chuyển sang 2 instances còn lại mà không downtime.

### Exercise 5.5: Test Stateless Design

```bash
python test_stateless.py
```

Script thực hiện:
1. Gửi request đầu → nhận `session_id` + `served_by` (instance A)
2. Gửi request tiếp theo với cùng `session_id` → có thể được serve bởi instance B hoặc C
3. Kiểm tra conversation history vẫn đầy đủ → chứng minh state được lưu trong Redis, không phải memory của instance

**Kết quả mong đợi:** `served_by` khác nhau giữa các request, nhưng `history` vẫn liên tục — stateless design hoạt động đúng.

### Checkpoint 5

- [x] Implement health và readiness checks
- [x] Implement graceful shutdown
- [x] Refactor code thành stateless
- [x] Hiểu load balancing với Nginx
- [x] Test stateless design

---

## Part 6: Final Project — Economics AI Chatbot

### Architecture

```
Browser
  └── GET /ui  →  Gradio ChatInterface (server-side Python handler)
                        │
                        ▼
              FastAPI app (port 8000)
                  ├── POST /ask  (X-API-Key required)
                  ├── GET  /health
                  ├── GET  /ready
                  └── GET  /metrics  (X-API-Key required)
                        │
                        ▼ (server-side only, key never leaves server)
                   Groq LLM API
              (llama-3.3-70b-versatile)
```

### File structure

```
06-lab-complete/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI + Gradio mount, lifespan, middleware
│   ├── config.py        # All settings from env vars (12-factor)
│   ├── auth.py          # X-API-Key verification dependency
│   ├── rate_limiter.py  # Sliding-window, 10 req/min per key
│   ├── cost_guard.py    # Monthly per-user budget ($10), Groq pricing
│   └── llm.py           # Groq client, economics system prompt, history
├── Dockerfile           # Multi-stage, non-root, < 500 MB
├── docker-compose.yml   # Single-service local stack
├── railway.toml         # Railway deployment config
├── requirements.txt     # fastapi, uvicorn, groq, gradio
└── .env.example         # Template — never commit .env
```

### Key design decisions

| Requirement | Implementation |
|---|---|
| LLM provider | Groq `llama-3.3-70b-versatile` via `groq` SDK |
| Economics-only | System prompt in `app/llm.py` — politely refuses off-topic questions |
| Frontend | Gradio `ChatInterface` mounted at `/ui` via `gr.mount_gradio_app` |
| Auth | `X-API-Key` header, verified in `app/auth.py` FastAPI dependency |
| Rate limiting | Sliding-window counter, 10 req/min, in `app/rate_limiter.py` |
| Cost guard | Monthly per-user cap ($10), Groq token pricing, in `app/cost_guard.py` |
| Health checks | `GET /health` (liveness) + `GET /ready` (readiness) |
| Graceful shutdown | `lifespan` async context manager + `SIGTERM` handler |
| Stateless | No in-process session state; Gradio history passed per-call |
| Secrets | All from env vars; `GROQ_API_KEY` + `AGENT_API_KEY` set on Railway |
| Container | Multi-stage Dockerfile, non-root `agent` user |

### Deploy steps (Railway)

```bash
cd 06-lab-complete

# 1. Login
railway login

# 2. Link to existing project or create new
railway init

# 3. Set environment variables
railway variables set GROQ_API_KEY=<your-groq-api-key>
railway variables set AGENT_API_KEY=<your-agent-api-key>
railway variables set ENVIRONMENT=production
railway variables set PORT=8000
railway variables set LOG_LEVEL=INFO
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set MONTHLY_BUDGET_USD=10.0

# 4. Deploy
railway up

# 5. Get public URL
railway domain
```

### Test commands

```bash
BASE=https://<your-domain>.railway.app
KEY=p1_bPh6iA4rV0TZhILIpfjKh5i3eBn4TEhENvsPnyZg

# Health check (no auth needed)
curl $BASE/health

# Readiness check
curl $BASE/ready

# Ask economics question (auth required)
curl -X POST $BASE/ask \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "What causes inflation?", "user_id": "student1"}'

# No key → 401
curl -X POST $BASE/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

# Rate limit test — 11th request → 429
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST $BASE/ask \
    -H "X-API-Key: $KEY" \
    -H "Content-Type: application/json" \
    -d '{"question": "What is GDP?", "user_id": "test"}'
done

# Gradio UI
open $BASE/ui
```

### Checklist

- [x] Agent trả lời câu hỏi qua REST API (`POST /ask`)
- [x] Economics-only via system prompt (off-topic → polite refusal)
- [x] Gradio frontend at `/ui`
- [x] Multi-stage Dockerfile (non-root, < 500 MB)
- [x] Config từ environment variables (12-factor)
- [x] API key authentication (`X-API-Key` header, 401 if missing/wrong)
- [x] Rate limiting (10 req/min per API key, sliding window)
- [x] Cost guard ($10/month per user, Groq token pricing)
- [x] Health check endpoint (`GET /health`)
- [x] Readiness check endpoint (`GET /ready`)
- [x] Graceful shutdown (lifespan + SIGTERM handler)
- [x] Structured JSON logging
- [x] Deploy lên Railway
- [x] Public URL hoạt động

