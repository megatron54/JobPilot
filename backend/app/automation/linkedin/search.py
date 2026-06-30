"""LinkedIn job search via the Voyager API.

Builds search parameters from the user's SearchCriteria and parses the
normalized response into lightweight job stubs. Detail enrichment (full
description, apply method, recruiter) is done separately in details.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..models import SearchCriteria
from . import parsing
from .client import LinkedInClient

logger = logging.getLogger("jobpilot.autopilot.linkedin.search")

# Voyager job search endpoint (cluster-based JSERP).
_SEARCH_PATH = "/search/hits"


@dataclass
class JobStub:
    """Minimal job info from a search result, before detail enrichment."""

    job_id: str
    title: str = ""
    company: str = ""
    company_id: str = ""
    location: str = ""
    workplace_type: str = ""
    listed_at: int = 0
    raw: dict = field(default_factory=dict)


def build_search_params(
    criteria: SearchCriteria, start: int = 0, count: int = 25
) -> dict:
    """Translate SearchCriteria into Voyager search query parameters."""
    keywords = " ".join(criteria.keywords) if criteria.keywords else ""
    params: dict[str, object] = {
        "decorationId": "com.linkedin.voyager.deco.jserp.WebJobSearchHitLite-14",
        "q": "jserpFilters",
        "query": keywords,
        "start": start,
        "count": min(count, 25),
        "origin": "JOB_SEARCH_RESULTS_PAGE",
    }

    filters: list[str] = []
    if criteria.geo_id:
        filters.append(f"geoUrn->{criteria.geo_id}")
    elif criteria.location:
        params["location"] = criteria.location

    workplace = _workplace_filter(criteria)
    if workplace:
        filters.append(f"workplaceType->{workplace}")
    if criteria.experience_levels:
        filters.append("experience->" + "|".join(criteria.experience_levels))
    if criteria.job_types:
        filters.append("jobType->" + "|".join(criteria.job_types))
    if criteria.posted_within_hours:
        seconds = criteria.posted_within_hours * 3600
        filters.append(f"timePostedRange->r{seconds}")

    if filters:
        params["filters"] = "List(" + ",".join(filters) + ")"

    return params


def _workplace_filter(criteria: SearchCriteria) -> str:
    """LinkedIn workplace type codes: 1=on-site, 2=remote, 3=hybrid."""
    codes = []
    if criteria.onsite:
        codes.append("1")
    if criteria.remote:
        codes.append("2")
    if criteria.hybrid:
        codes.append("3")
    return "|".join(codes)


async def search_jobs(
    client: LinkedInClient,
    criteria: SearchCriteria,
    start: int = 0,
    count: int = 25,
) -> list[JobStub]:
    """Run one page of job search and return parsed stubs."""
    params = build_search_params(criteria, start=start, count=count)
    payload = await client.get(_SEARCH_PATH, params=params)
    return parse_job_stubs(payload)


def parse_job_stubs(payload: dict) -> list[JobStub]:
    """Parse JobPosting entities from a normalized search response."""
    index = parsing.build_index(payload)
    stubs: list[JobStub] = []
    seen: set[str] = set()

    for item in parsing.included_of_type(payload, "JobPosting"):
        urn = item.get("entityUrn", "")
        job_id = parsing.job_id_from_urn(urn)
        if not job_id or job_id in seen:
            continue
        seen.add(job_id)

        company, company_id = _resolve_company(item, index)
        stubs.append(
            JobStub(
                job_id=job_id,
                title=parsing.first(item.get("title")),
                company=company,
                company_id=company_id,
                location=parsing.first(item.get("formattedLocation")),
                workplace_type=_workplace_label(item),
                listed_at=int(item.get("listedAt") or 0),
                raw=item,
            )
        )

    return stubs


def _resolve_company(job: dict, index: dict[str, dict]) -> tuple[str, str]:
    details = job.get("companyDetails") or {}
    company_urn = ""
    if isinstance(details, dict):
        # Shape varies; look for any nested company URN reference.
        company_urn = (
            details.get("company")
            or _nested_company_urn(details)
            or ""
        )
    entity = index.get(company_urn, {}) if company_urn else {}
    name = parsing.first(entity.get("name"), job.get("companyName"))
    company_id = parsing.job_id_from_urn(company_urn) if company_urn else ""
    return name, company_id


def _nested_company_urn(details: dict) -> str:
    for value in details.values():
        if isinstance(value, dict):
            urn = value.get("company") or value.get("*company")
            if isinstance(urn, str):
                return urn
    return ""


def _workplace_label(job: dict) -> str:
    if job.get("workRemoteAllowed"):
        return "remote"
    types = job.get("workplaceTypes") or []
    if isinstance(types, list) and types:
        label = str(types[0]).lower()
        if "remote" in label:
            return "remote"
        if "hybrid" in label:
            return "hybrid"
        if "site" in label or "onsite" in label:
            return "onsite"
    return ""
