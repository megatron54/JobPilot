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
        try:
            # Compute (and reserve) the required spacing under the lock, but
            # sleep *outside* of it, so other concurrent callers can proceed
            # to acquire the semaphore/compute their own spacing instead of
            # being serialized behind this call's sleep (which previously
            # collapsed effective concurrency to 1 during delays).
            async with self._lock:
                now = time.monotonic()
                wait = random.uniform(self._min, self._max)
                elapsed = now - self._last_call
                sleep_for = max(0.0, wait - elapsed)
                # Reserve the next slot immediately so overlapping callers
                # still get spaced-out slots rather than racing on the same
                # `_last_call` timestamp.
                self._last_call = now + sleep_for

            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
        except BaseException:
            # Guarantee the semaphore permit is not leaked if acquire is
            # cancelled (e.g. during the sleep) or otherwise fails.
            self._sem.release()
            raise

    def release(self) -> None:
        self._sem.release()

    async def __aenter__(self) -> "RateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.release()
