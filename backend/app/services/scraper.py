"""Web scraper for job postings - supports LinkedIn, InfoJobs, Indeed, and generic pages."""

import re
import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.security import assert_safe_http_url

logger = logging.getLogger("jobpilot.scraper")

MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB cap to avoid DoS via huge/malicious responses

# Headers to mimic a real browser (avoid bot detection)
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


async def scrape_job_url(url: str, use_browser: bool = False) -> dict:
    """Scrape a job posting URL and return structured raw content.
    
    Args:
        url: The job posting URL
        use_browser: Force using Playwright browser (for JS-heavy pages)
    
    Returns:
        dict with keys: raw_text, url, source, title (if found)
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    try:
        assert_safe_http_url(url)
    except Exception as e:
        logger.warning(f"Rejected unsafe URL {url}: {e}")
        return {
            "raw_text": "",
            "url": url,
            "source": _detect_source(domain),
            "error": "URL not allowed",
        }

    try:
        # Try Playwright first for LinkedIn (it requires JS rendering)
        if use_browser or "linkedin.com" in domain:
            html = await _fetch_with_browser_fallback(url)
        else:
            html = await _fetch_page(url)
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return {
            "raw_text": "",
            "url": url,
            "source": _detect_source(domain),
            "error": f"Failed to fetch page: {str(e)}",
        }

    # Route to specialized parser based on domain
    if "linkedin.com" in domain:
        result = _parse_linkedin(html, url)
        # If LinkedIn returned very little content, it's likely behind a login wall
        if len(result.get("raw_text", "")) < 100:
            result["warning"] = (
                "Limited content extracted. LinkedIn may require authentication. "
                "Consider pasting the job description manually."
            )
        return result
    elif "infojobs" in domain:
        return _parse_infojobs(html, url)
    elif "indeed" in domain:
        return _parse_indeed(html, url)
    else:
        return _parse_generic(html, url, domain)


async def _fetch_page(url: str) -> str:
    """Fetch page HTML with browser-like headers, capped in size.

    Validates every redirect hop to prevent SSRF bypass via redirection to
    internal/private addresses.
    """

    async def _validate_redirect(request: httpx.Request) -> None:
        assert_safe_http_url(str(request.url))

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        max_redirects=5,
        headers=BROWSER_HEADERS,
        event_hooks={"request": [_validate_redirect]},
    ) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            chunks = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise ValueError("Response too large")
                chunks.append(chunk)
            return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")


async def _fetch_with_browser_fallback(url: str) -> str:
    """Try Playwright first, fall back to httpx if not available."""
    try:
        from app.services.scraper_advanced import is_available, scrape_with_browser
        if is_available():
            logger.info(f"Using Playwright browser for: {url}")
            return await scrape_with_browser(url)
    except Exception as e:
        logger.warning(f"Playwright failed, falling back to httpx: {e}")
    
    # Fallback to simple HTTP request
    return await _fetch_page(url)


def _detect_source(domain: str) -> str:
    """Detect the job board source from domain."""
    if "linkedin" in domain:
        return "linkedin"
    elif "infojobs" in domain:
        return "infojobs"
    elif "indeed" in domain:
        return "indeed"
    elif "glassdoor" in domain:
        return "glassdoor"
    elif "welcometothejungle" in domain:
        return "welcometothejungle"
    return "web"


def _clean_text(text: str) -> str:
    """Clean extracted text - remove extra whitespace, normalize."""
    # Remove excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove excessive spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Strip lines
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


# ─── LinkedIn ──────────────────────────────────────────────────────────

def _parse_linkedin(html: str, url: str) -> dict:
    """Parse LinkedIn job posting.
    
    LinkedIn public job pages have structured content even without login.
    The main job description is in specific containers.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = ""
    title_el = soup.find("h1") or soup.find("h2", class_=re.compile(r"job|title", re.I))
    if title_el:
        title = title_el.get_text(strip=True)

    # Company
    company = ""
    company_el = soup.find("a", class_=re.compile(r"company", re.I))
    if not company_el:
        company_el = soup.find(attrs={"data-tracking-control-name": re.compile(r"company", re.I)})
    if company_el:
        company = company_el.get_text(strip=True)

    # Job description - LinkedIn uses different containers
    description = ""
    desc_containers = soup.find_all(
        class_=re.compile(r"description|show-more-less-html|job-details", re.I)
    )
    if desc_containers:
        description = "\n\n".join(c.get_text(separator="\n") for c in desc_containers)
    
    # Fallback: try the main content area
    if not description:
        main = soup.find("main") or soup.find(class_=re.compile(r"core-section"))
        if main:
            description = main.get_text(separator="\n")

    # Location
    location = ""
    loc_el = soup.find(class_=re.compile(r"location|workplace", re.I))
    if loc_el:
        location = loc_el.get_text(strip=True)

    # Criteria (experience level, employment type, etc.)
    criteria = []
    criteria_items = soup.find_all(class_=re.compile(r"criteria|insight", re.I))
    for item in criteria_items:
        text = item.get_text(strip=True)
        if text:
            criteria.append(text)

    raw_text = f"{title}\n{company}\n{location}\n\n{_clean_text(description)}"
    if criteria:
        raw_text += "\n\n" + "\n".join(criteria)

    return {
        "raw_text": _clean_text(raw_text),
        "url": url,
        "source": "linkedin",
        "title": title,
        "company": company,
        "location": location,
    }


# ─── InfoJobs ──────────────────────────────────────────────────────────

def _parse_infojobs(html: str, url: str) -> dict:
    """Parse InfoJobs job posting."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    title_el = soup.find("h1")
    if title_el:
        title = title_el.get_text(strip=True)

    company = ""
    company_el = soup.find(class_=re.compile(r"company-name|empresa", re.I))
    if company_el:
        company = company_el.get_text(strip=True)

    # InfoJobs puts description in specific sections
    description = ""
    desc_el = soup.find(class_=re.compile(r"description|requisitos|detalle", re.I))
    if desc_el:
        description = desc_el.get_text(separator="\n")
    
    # Fallback to article or main
    if not description:
        article = soup.find("article") or soup.find("main")
        if article:
            description = article.get_text(separator="\n")

    raw_text = f"{title}\n{company}\n\n{_clean_text(description)}"

    return {
        "raw_text": _clean_text(raw_text),
        "url": url,
        "source": "infojobs",
        "title": title,
        "company": company,
        "location": "",
    }


# ─── Indeed ────────────────────────────────────────────────────────────

def _parse_indeed(html: str, url: str) -> dict:
    """Parse Indeed job posting."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    title_el = soup.find(class_=re.compile(r"jobTitle|job-title", re.I)) or soup.find("h1")
    if title_el:
        title = title_el.get_text(strip=True)

    company = ""
    company_el = soup.find(attrs={"data-testid": "inlineHeader-companyName"})
    if not company_el:
        company_el = soup.find(class_=re.compile(r"companyName|company", re.I))
    if company_el:
        company = company_el.get_text(strip=True)

    description = ""
    desc_el = soup.find(id="jobDescriptionText") or soup.find(
        class_=re.compile(r"jobDescription|job-description", re.I)
    )
    if desc_el:
        description = desc_el.get_text(separator="\n")

    location = ""
    loc_el = soup.find(attrs={"data-testid": "job-location"})
    if not loc_el:
        loc_el = soup.find(class_=re.compile(r"location|companyLocation", re.I))
    if loc_el:
        location = loc_el.get_text(strip=True)

    raw_text = f"{title}\n{company}\n{location}\n\n{_clean_text(description)}"

    return {
        "raw_text": _clean_text(raw_text),
        "url": url,
        "source": "indeed",
        "title": title,
        "company": company,
        "location": location,
    }


# ─── Generic ──────────────────────────────────────────────────────────

def _parse_generic(html: str, url: str, domain: str) -> dict:
    """Parse any generic job posting page."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise: scripts, styles, nav, footer, header
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    title = ""
    title_el = soup.find("h1")
    if title_el:
        title = title_el.get_text(strip=True)

    # Try to find the main content area
    content = ""
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(role="main")
        or soup.find(class_=re.compile(r"content|job|offer|posting|description", re.I))
    )
    
    if main:
        content = main.get_text(separator="\n")
    else:
        # Fallback: get body text
        body = soup.find("body")
        if body:
            content = body.get_text(separator="\n")

    raw_text = f"{title}\n\n{_clean_text(content)}"

    return {
        "raw_text": _clean_text(raw_text),
        "url": url,
        "source": _detect_source(domain),
        "title": title,
        "company": "",
        "location": "",
    }
