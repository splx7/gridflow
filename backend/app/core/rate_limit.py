"""Simple in-memory rate limiting for auth endpoints."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Token bucket rate limiter keyed by client IP."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def check(self, request: Request) -> None:
        """Raise 429 if rate limit exceeded."""
        now = time.time()
        key = self._get_client_ip(request)
        self._cleanup(key, now)

        if len(self._requests[key]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s.",
            )

        self._requests[key].append(now)


# Singleton instances
auth_limiter = RateLimiter(max_requests=10, window_seconds=60)
simulation_limiter = RateLimiter(max_requests=10, window_seconds=60)
weather_limiter = RateLimiter(max_requests=5, window_seconds=60)
report_limiter = RateLimiter(max_requests=5, window_seconds=60)
sensitivity_limiter = RateLimiter(max_requests=3, window_seconds=60)
