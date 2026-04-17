"""Sliding-window rate limiter — in-memory, safe for single-instance deploy."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings

_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(user_key: str) -> None:
    """Raise 429 if user_key exceeded RATE_LIMIT_PER_MINUTE requests in last 60 s."""
    now = time.time()
    window = _windows[user_key]

    # Drop timestamps outside the 60-second window
    while window and window[0] < now - 60:
        window.popleft()

    if len(window) >= settings.rate_limit_per_minute:
        oldest = window[0]
        retry_after = int(oldest + 60 - now) + 1
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": settings.rate_limit_per_minute,
                "retry_after_seconds": retry_after,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                "X-RateLimit-Remaining": "0",
            },
        )

    window.append(now)
