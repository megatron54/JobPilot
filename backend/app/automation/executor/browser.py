"""Playwright browser manager for action execution.

Launches a VISIBLE Chromium so the user can supervise every write action
(apply, connect). Injects the LinkedIn session cookies so the browser is
already logged in. Used only for the small fraction of operations that require
real browser interaction (see docs/AUTOPILOT_PLAN.md sections 10-11).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ..session import LinkedInSession

logger = logging.getLogger("jobpilot.autopilot.browser")

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class BrowserUnavailableError(Exception):
    """Playwright or its browsers are not installed."""


def _linkedin_cookies(session: LinkedInSession) -> list[dict]:
    cookies: list[dict] = []
    if session.li_at:
        cookies.append({
            "name": "li_at",
            "value": session.li_at,
            "domain": ".linkedin.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
        })
    if session.jsessionid:
        cookies.append({
            "name": "JSESSIONID",
            "value": f'"{session.jsessionid}"',
            "domain": ".linkedin.com",
            "path": "/",
            "secure": True,
        })
    return cookies


@asynccontextmanager
async def browser_page(
    session: LinkedInSession | None = None,
    headless: bool = False,
    inject_linkedin: bool = True,
):
    """Yield a Playwright page with optional LinkedIn auth.

    Visible by default so the user can watch and intervene. Raises
    BrowserUnavailableError if Playwright/browsers are missing.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - import guard
        raise BrowserUnavailableError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    pw = await async_playwright().start()
    try:
        try:
            browser = await pw.chromium.launch(headless=headless)
        except Exception as exc:  # pragma: no cover - browser binary missing
            raise BrowserUnavailableError(
                "Chromium not installed. Run: playwright install chromium"
            ) from exc

        context = await browser.new_context(
            user_agent=_UA,
            viewport={"width": 1440, "height": 900},
            locale="es-ES",
            timezone_id="Europe/Madrid",
        )
        if inject_linkedin and session and session.has_session:
            await context.add_cookies(_linkedin_cookies(session))

        await _apply_stealth(context)

        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()
            await browser.close()
    finally:
        await pw.stop()


async def _apply_stealth(context) -> None:
    """Minimal anti-detection: hide the webdriver flag.

    Uses playwright-stealth if available; otherwise applies a small init script.
    """
    try:
        from playwright_stealth import stealth_async  # type: ignore

        # stealth applies per-page; install on new pages.
        context.on("page", lambda p: _safe_stealth(stealth_async, p))
    except ImportError:
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )


def _safe_stealth(stealth_async, page) -> None:  # pragma: no cover - event cb
    import asyncio

    asyncio.ensure_future(stealth_async(page))
