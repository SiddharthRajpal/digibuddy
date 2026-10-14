"""Tiny in-memory sliding-window rate limiter for auth endpoints.

Good enough for a single API process. Swap for Redis when running several workers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


auth_limiter = SlidingWindowLimiter()


async def limit_auth(request: Request) -> None:
    """Login and signup: strict limit against password guessing."""
    _limit(request, get_settings().auth_rate_limit_per_minute)


async def limit_refresh(request: Request) -> None:
    """Token refresh runs on every page load, so it gets a looser limit."""
    _limit(request, get_settings().refresh_rate_limit_per_minute)


def client_ip(request: Request) -> str:
    """Caller's IP. Behind the frontend proxy, use the first X-Forwarded-For hop."""
    if get_settings().trust_forwarded_for:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _limit(request: Request, limit: int) -> None:
    client = client_ip(request)
    route = request.url.path
    if not auth_limiter.check(f"{client}:{route}", limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a minute and try again.",
        )
