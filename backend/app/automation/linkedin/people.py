"""Find recruiters / hiring contacts at a company via the Voyager people search."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from . import parsing
from .client import LinkedInClient

logger = logging.getLogger("jobpilot.autopilot.linkedin.people")

_SEARCH_PATH = "/search/blended"

# Titles that indicate a recruiting / talent / HR contact.
_RECRUITER_TITLES = (
    "Talent Acquisition",
    "Recruiter",
    "Technical Recruiter",
    "People",
    "Human Resources",
    "Hiring",
)


@dataclass
class Recruiter:
    name: str
    title: str = ""
    profile_url: str = ""
    public_id: str = ""


async def find_recruiters(
    client: LinkedInClient,
    company_id: str,
    title_query: str = "Talent Acquisition",
    count: int = 5,
) -> list[Recruiter]:
    """Search people at a company filtered by a recruiting-related title."""
    if not company_id:
        return []

    params = {
        "q": "all",
        "query": title_query,
        "start": 0,
        "count": min(count, 10),
        "origin": "FACETED_SEARCH",
        "filters": f"List(resultType->PEOPLE,currentCompany->{company_id})",
    }
    try:
        payload = await client.get(_SEARCH_PATH, params=params)
    except Exception as exc:  # noqa: BLE001 - recruiter search is best-effort
        logger.info("Recruiter search failed (non-fatal): %s", exc)
        return []

    return parse_recruiters(payload)


def parse_recruiters(payload: dict) -> list[Recruiter]:
    out: list[Recruiter] = []
    for profile in parsing.included_of_type(payload, "MiniProfile"):
        first = parsing.first(profile.get("firstName"))
        last = parsing.first(profile.get("lastName"))
        name = f"{first} {last}".strip()
        if not name:
            continue
        public_id = parsing.first(profile.get("publicIdentifier"))
        out.append(
            Recruiter(
                name=name,
                title=parsing.first(profile.get("occupation")),
                profile_url=f"https://www.linkedin.com/in/{public_id}/" if public_id else "",
                public_id=public_id,
            )
        )
    return out


def is_recruiter_title(title: str) -> bool:
    lowered = title.lower()
    return any(t.lower() in lowered for t in _RECRUITER_TITLES)
