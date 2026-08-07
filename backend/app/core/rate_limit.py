"""Minimal in-memory rate limiting middleware.

No external dependency: a simple fixed-window counter per client address,
applied to the whole API. This is a local, single-user desktop tool, so the
goal is not to defend against a distributed attacker but to prevent a single
misbehaving client (or a compromised frontend/XSS) from hammering the LLM,
the scraper, or the filesystem endlessly.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: float = 60.0):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = self._hits[client]

        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests, please slow down."},
                headers={"Retry-After": str(int(self.window_seconds))},
            )

        bucket.append(now)
        return await call_next(request)
