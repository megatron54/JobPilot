"""Tests for the rate limiter."""

from __future__ import annotations

import time

import pytest

from app.automation.linkedin.rate_limiter import RateLimiter

pytestmark = pytest.mark.asyncio


async def test_enforces_minimum_spacing() -> None:
    rl = RateLimiter(min_delay_s=0.05, max_delay_s=0.05, max_concurrent=1)
    start = time.monotonic()
    async with rl:
        pass
    async with rl:
        pass
    elapsed = time.monotonic() - start
    # Second acquire must wait ~0.05s after the first.
    assert elapsed >= 0.04


async def test_concurrency_limit() -> None:
    rl = RateLimiter(min_delay_s=0.0, max_delay_s=0.0, max_concurrent=2)
    # Acquire twice without releasing; a third must be blocked.
    await rl.acquire()
    await rl.acquire()
    import asyncio

    third = asyncio.create_task(rl.acquire())
    await asyncio.sleep(0.05)
    assert not third.done()
    rl.release()
    await asyncio.wait_for(third, timeout=1)
    assert third.done()
    rl.release()
    rl.release()
