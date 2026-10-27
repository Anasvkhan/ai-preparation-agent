"""Small in-memory rate limiter for auth endpoints (single API process is enough for the FYP)."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, max_calls: int, per_seconds: int):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._calls: dict[str, deque] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        key = f"{request.url.path}:{request.client.host if request.client else 'unknown'}"
        now = time.monotonic()
        calls = self._calls[key]
        while calls and now - calls[0] > self.per_seconds:
            calls.popleft()
        if len(calls) >= self.max_calls:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, try again in a minute")
        calls.append(now)


auth_limiter = RateLimiter(max_calls=10, per_seconds=60)
