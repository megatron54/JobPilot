"""LinkedIn guest (unauthenticated) job search.

Uses LinkedIn's public `jobs-guest` endpoints, which require NO authentication
(no li_at cookie, no CSRF). This is the safest discovery source - minimal ban
risk - at the cost of less data than the Voyager API (no applicant count, no
Easy Apply flag, no recruiter). Used as the default discovery source; Voyager
enriches only the top matches.

Ported from the MIT-licensed `linkedin-search` skill in
github.com/MadsLorentzen/ai-job-search (TypeScript -> Python).

> Personal use only - automated access is against LinkedIn's ToS; keep volume low.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import logging
import random
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("jobpilot.autopilot.linkedin.guest")

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}


@dataclass
class GuestJobCard:
    id: str
    title: str
    company: str = ""
    company_url: str = ""
    location: str = ""
    date: str = ""
    url: str = ""


@dataclass
class GuestJobDetail:
    id: str
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    seniority: str = ""
    employment_type: str = ""
    job_function: str = ""
    industries: str = ""
    apply_url: str = ""
    criteria: dict = field(default_factory=dict)


class GuestFetchError(Exception):
    """Raised when the guest endpoint fails after retries."""


def jobage_to_tpr(days: int) -> str:
    """Convert a job-age in days to LinkedIn's f_TPR seconds value."""
    if not days or days <= 0 or days >= 9999:
        return ""
    return f"r{days * 86400}"


def work_type_flag(mode: str) -> str:
    """Workplace-type flag: on-site=1, remote=2, hybrid=3."""
    return {"remote": "2", "hybrid": "3", "onsite": "1", "on-site": "1"}.get(
        (mode or "").lower(), ""
    )


def build_search_url(
    keywords: str, location: str, jobage_days: int = 7,
    remote: str = "", page: int = 1,
) -> str:
    params: list[tuple[str, str]] = []
    if keywords:
        params.append(("keywords", keywords))
    if location:
        params.append(("location", location))
    tpr = jobage_to_tpr(jobage_days)
    if tpr:
        params.append(("f_TPR", tpr))
    wt = work_type_flag(remote)
    if wt:
        params.append(("f_WT", wt))
    params.append(("start", str((page - 1) * 10)))
    return str(httpx.URL(SEARCH_URL, params=params))


async def _html_fetch(client: httpx.AsyncClient, url: str, max_retries: int = 6) -> str:
    """Fetch HTML with exponential backoff on 429/5xx. Returns '' on 404."""
    delay = 0.5
    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(url, headers=_HEADERS, follow_redirects=True)
        except httpx.HTTPError as exc:
            if attempt == max_retries:
                raise GuestFetchError(f"Request failed: {exc}") from exc
            await asyncio.sleep(delay + random.uniform(0, 0.5))
            delay = min(delay * 2, 8.0)
            continue

        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == max_retries:
                raise GuestFetchError(f"Request failed: {resp.status_code}")
            await asyncio.sleep(delay + random.uniform(0, 0.5))
            delay = min(delay * 2, 8.0)
            continue
        if resp.status_code == 404:
            return ""
        if resp.status_code >= 400:
            raise GuestFetchError(f"Request failed: {resp.status_code}")
        return resp.text
    raise GuestFetchError("Request failed after max retries")


# --- HTML parsing (regex; markup is shallow and stable) -----------------


def _decode(text: str) -> str:
    return html_lib.unescape(text)


def _strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _clean(text: str) -> str:
    return _decode(_strip_tags(text))


def parse_job_cards(html: str) -> list[GuestJobCard]:
    """Parse the guest search response (a flat list of <li> job cards)."""
    cards: list[GuestJobCard] = []
    chunks = re.split(r'data-entity-urn="urn:li:jobPosting:', html)[1:]

    for chunk in chunks:
        id_match = re.match(r"^(\d+)", chunk)
        if not id_match:
            continue
        job_id = id_match.group(1)

        link = re.search(
            r'class="base-card__full-link[^"]*"[^>]*href="([^"]+)"', chunk, re.I
        )
        url = _decode(link.group(1)).split("?")[0] if link else ""

        title = ""
        h3 = re.search(r'class="base-search-card__title"[^>]*>([\s\S]*?)</h3>', chunk, re.I)
        if h3:
            title = _clean(h3.group(1))
        if not title:
            sr = re.search(r'class="sr-only"[^>]*>([\s\S]*?)</span>', chunk, re.I)
            if sr:
                title = _clean(sr.group(1))
        if not title:
            continue

        company = ""
        company_url = ""
        sub = re.search(
            r'class="base-search-card__subtitle"[^>]*>([\s\S]*?)</h4>', chunk, re.I
        )
        if sub:
            a = re.search(r'href="([^"]+)"', sub.group(1), re.I)
            if a:
                company_url = _decode(a.group(1)).split("?")[0]
            company = _clean(sub.group(1))

        loc = re.search(
            r'class="job-search-card__location"[^>]*>([\s\S]*?)</span>', chunk, re.I
        )
        location = _clean(loc.group(1)) if loc else ""
        dt = re.search(
            r'class="job-search-card__listdate[^"]*"[^>]*datetime="([^"]+)"', chunk, re.I
        )
        date = dt.group(1) if dt else ""

        cards.append(GuestJobCard(
            id=job_id, title=title, company=company, company_url=company_url,
            location=location, date=date,
            url=url or f"https://www.linkedin.com/jobs/view/{job_id}",
        ))
    return cards


def parse_job_detail(html: str, job_id: str) -> GuestJobDetail:
    """Parse the single-job guest detail page."""
    title_m = re.search(
        r'class="(?:top-card-layout__title|topcard__title)[^"]*"[^>]*>([\s\S]*?)</h[12]>',
        html, re.I,
    )
    org_m = re.search(
        r'class="topcard__org-name-link[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>',
        html, re.I,
    )
    company = _clean(org_m.group(2)) if org_m else ""

    loc_m = re.search(
        r'class="topcard__flavor topcard__flavor--bullet"[^>]*>([\s\S]*?)</span>', html, re.I
    )
    location = _clean(loc_m.group(1)) if loc_m else ""

    description = ""
    desc_m = re.search(
        r'class="(?:show-more-less-html__markup|description__text[^"]*)"[^>]*>([\s\S]*?)</div>',
        html, re.I,
    )
    if desc_m:
        with_breaks = re.sub(r"<\s*br\s*/?>", "\n", desc_m.group(1), flags=re.I)
        with_breaks = re.sub(r"</(p|li|ul|ol|div|h\d)>", "\n", with_breaks, flags=re.I)
        description = re.sub(r"\n{3,}", "\n\n", _decode(_strip_tags(with_breaks))).strip()

    criteria: dict[str, str] = {}
    item_re = re.compile(
        r'class="description__job-criteria-subheader"[^>]*>([\s\S]*?)</h3>'
        r'[\s\S]*?class="description__job-criteria-text[^"]*"[^>]*>([\s\S]*?)</span>',
        re.I,
    )
    for cm in item_re.finditer(html):
        criteria[_clean(cm.group(1)).lower()] = _clean(cm.group(2))

    apply_m = re.search(r'class="topcard__link[^"]*"[^>]*href="([^"]+)"', html, re.I)
    apply_url = _decode(apply_m.group(1)).split("?")[0] if apply_m else ""

    return GuestJobDetail(
        id=job_id,
        title=_clean(title_m.group(1)) if title_m else "",
        company=company,
        location=location,
        description=description,
        seniority=criteria.get("seniority level", ""),
        employment_type=criteria.get("employment type", ""),
        job_function=criteria.get("job function", ""),
        industries=criteria.get("industries", ""),
        apply_url=apply_url,
        criteria=criteria,
    )


# --- Public async API ---------------------------------------------------


async def search_guest(
    keywords: str, location: str, jobage_days: int = 7,
    remote: str = "", page: int = 1, timeout_s: float = 15.0,
) -> list[GuestJobCard]:
    """Run one page of guest job search."""
    url = build_search_url(keywords, location, jobage_days, remote, page)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        html = await _html_fetch(client, url)
    return parse_job_cards(html)


async def fetch_guest_detail(job_id: str, timeout_s: float = 15.0) -> GuestJobDetail:
    """Fetch a single job's guest detail page."""
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        html = await _html_fetch(client, f"{DETAIL_URL}/{job_id}")
    return parse_job_detail(html, job_id)
