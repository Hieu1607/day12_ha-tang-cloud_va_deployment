"""Monthly per-user cost guard — in-memory, resets each calendar month."""
import time
import logging
from collections import defaultdict

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

# Groq llama-3.3-70b-versatile pricing (per 1K tokens, USD)
_INPUT_COST_PER_1K = 0.00059
_OUTPUT_COST_PER_1K = 0.00079

# { "user_key:YYYY-MM": cumulative_cost_usd }
_monthly_spend: dict[str, float] = defaultdict(float)


def _month_key(user_key: str) -> str:
    return f"{user_key}:{time.strftime('%Y-%m')}"


def check_budget(user_key: str) -> None:
    """Raise 402 if user has exceeded MONTHLY_BUDGET_USD this month."""
    key = _month_key(user_key)
    spent = _monthly_spend[key]
    if spent >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "spent_usd": round(spent, 4),
                "budget_usd": settings.monthly_budget_usd,
                "resets_at": "1st of next month",
            },
        )
    if spent >= settings.monthly_budget_usd * 0.8:
        logger.warning(f"User {user_key[:8]} at {spent/settings.monthly_budget_usd*100:.0f}% monthly budget")


def record_usage(user_key: str, input_tokens: int, output_tokens: int) -> float:
    """Record token usage and return cost of this call in USD."""
    cost = (input_tokens / 1000) * _INPUT_COST_PER_1K + (output_tokens / 1000) * _OUTPUT_COST_PER_1K
    key = _month_key(user_key)
    _monthly_spend[key] += cost
    logger.info(f"Cost: user={user_key[:8]} call=${cost:.5f} month_total=${_monthly_spend[key]:.4f}")
    return cost
