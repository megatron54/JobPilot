"""Advanced scraper using Playwright for JavaScript-heavy pages (LinkedIn, etc.).

This is an optional module - falls back to httpx+BeautifulSoup if Playwright is not installed.
Install with: pip install jobpilot[scraping] && playwright install chromium
"""

import logging
import re

from app.core.security import assert_safe_http_url

logger = logging.getLogger("jobpilot.scraper_advanced")

_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    """Check if Playwright is installed and available."""
    return _PLAYWRIGHT_AVAILABLE


async def scrape_with_browser(url: str, wait_selector: str | None = None, wait_time: int = 3000) -> str:
    """Scrape a page using a headless browser (Playwright).
    
    Use this for pages that require JavaScript rendering (LinkedIn login wall, SPAs, etc.).
    
    Args:
        url: The URL to scrape
        wait_selector: Optional CSS selector to wait for before extracting content
        wait_time: Milliseconds to wait after page load (default 3s)
    
    Returns:
        Raw HTML of the rendered page
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is not installed. Install with: "
            "pip install playwright && playwright install chromium"
        )

    assert_safe_http_url(url)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="es-ES",
        )
        
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for specific content if selector provided
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.warning(f"Selector '{wait_selector}' not found, continuing anyway")
            
            # Extra wait for dynamic content
            await page.wait_for_timeout(wait_time)
            
            # Try to click "show more" buttons (common on LinkedIn)
            show_more_selectors = [
                "button[aria-label*='more']",
                "button[aria-label*='Show']",
                ".show-more-less-html__button",
                "[data-tracking-control-name*='show_more']",
            ]
            for selector in show_more_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(500)
                except Exception:
                    continue
            
            html = await page.content()
            return html
            
        finally:
            await browser.close()


async def scrape_linkedin_with_browser(url: str) -> str:
    """Specialized LinkedIn scraper using browser.
    
    LinkedIn requires JS rendering for most content.
    Public job postings (/jobs/view/...) are partially accessible without login.
    """
    return await scrape_with_browser(
        url,
        wait_selector=".show-more-less-html, .description, .job-details",
        wait_time=3000,
    )
