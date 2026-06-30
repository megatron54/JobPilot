"""Token-bucket rate limiter with human-like random jitter.

Used to throttle requests to the LinkedIn Voyager API to stay well under
detection thresholds (see docs/AUTOPILOT_PLAN.md section 7).
"""

from __future__ import annotations

import asyncio
import random
import time


class RateLimiter:
    """Async rate limiter: enforces a minimum spacing between calls plus a
    bounded concurrent-request semaphore. Spacing uses random jitter so the
    request cadence does not look mechanical.
    """

    def __init__(
        self,
        min_delay_s: float = 2.0,
        max_delay_s: float = 5.0,
        max_concurrent: int = 5,
    ) -> None:
        self._min = min_delay_s
        self._max = max_delay_s
        self._sem = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()
        self._last_call: float = 0.0

    async def acquire(self) -> None:
        await self._sem.acquire()
        async with self._lock:
            now = time.monotonic()
            wait = random.uniform(self._min, self._max)
            elapsed = now - self._last_call
            if elapsed < wait:
                await asyncio.sleep(wait - elapsed)
            self._last_call = time.monotonic()

    def release(self) -> None:
        self._sem.release()

    async def __aenter__(self) -> "RateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.release()
