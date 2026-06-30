"""Fetch full job details from the Voyager API.

Enriches a job stub with the full description, apply method (Easy Apply vs
external), salary hints, and the hiring team / recruiter when exposed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from . import parsing
from .client import LinkedInClient

logger = logging.getLogger("jobpilot.autopilot.linkedin.details")

_DETAIL_PATH = "/jobs/jobPostings/{job_id}"
_DECORATION = "com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65"


@dataclass
class JobDetails:
    job_id: str
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    apply_method: str = ""          # easy_apply / external
    external_url: str = ""
    workplace_type: str = ""
    listed_at: int = 0
    num_applicants: int = 0
    recruiter_name: str = ""
    recruiter_url: str = ""
    raw: dict = field(default_factory=dict)


async def fetch_job_details(client: LinkedInClient, job_id: str) -> JobDetails:
    path = _DETAIL_PATH.format(job_id=job_id)
    payload = await client.get(path, params={"decorationId": _DECORATION})
    return parse_job_details(job_id, payload)


def parse_job_details(job_id: str, payload: dict) -> JobDetails:
    data = payload.get("data") or payload
    apply_method, external_url = _parse_apply_method(data)
    recruiter_name, recruiter_url = _parse_recruiter(payload)

    return JobDetails(
        job_id=job_id,
        title=parsing.first(data.get("title")),
        company=_parse_company_name(payload, data),
        location=parsing.first(data.get("formattedLocation")),
        description=parsing.text_of(data.get("description")),
        apply_method=apply_method,
        external_url=external_url,
        workplace_type=_workplace_label(data),
        listed_at=int(data.get("listedAt") or 0),
        num_applicants=int(data.get("applies") or 0),
        recruiter_name=recruiter_name,
        recruiter_url=recruiter_url,
        raw=data,
    )


def _parse_apply_method(data: dict) -> tuple[str, str]:
    method = data.get("applyMethod")
    if not isinstance(method, dict):
        return "", ""
    for key, value in method.items():
        if "ComplexOnsiteApply" in key or "EasyApply" in key:
            return "easy_apply", ""
        if "OffsiteApply" in key or "External" in key:
            url = ""
            if isinstance(value, dict):
                url = parsing.first(
                    value.get("companyApplyUrl"), value.get("applyStartersPreferenceVoid")
                )
            return "external", url
    return "", ""


def _parse_company_name(payload: dict, data: dict) -> str:
    companies = parsing.included_of_type(payload, "Company")
    if companies:
        name = parsing.first(companies[0].get("name"))
        if name:
            return name
    details = data.get("companyDetails")
    if isinstance(details, dict):
        return parsing.first(details.get("companyName"), data.get("companyName"))
    return parsing.first(data.get("companyName"))


def _parse_recruiter(payload: dict) -> tuple[str, str]:
    """Best-effort extraction of the hiring team / poster profile."""
    for member in parsing.included_of_type(payload, "JobPostingHiringTeamMember"):
        name = _member_name(member)
        if name:
            return name, _member_url(member)

    # Fallback: any Profile entity in the included array.
    for profile in parsing.included_of_type(payload, "MiniProfile"):
        name = _member_name(profile)
        if name:
            return name, _member_url(profile)
    return "", ""


def _member_name(entity: dict) -> str:
    first = parsing.first(entity.get("firstName"))
    last = parsing.first(entity.get("lastName"))
    full = f"{first} {last}".strip()
    return full or parsing.first(entity.get("title"))


def _member_url(entity: dict) -> str:
    public_id = parsing.first(entity.get("publicIdentifier"))
    if public_id:
        return f"https://www.linkedin.com/in/{public_id}/"
    return ""


def _workplace_label(data: dict) -> str:
    if data.get("workRemoteAllowed"):
        return "remote"
    types = data.get("workplaceTypes") or []
    if isinstance(types, list) and types:
        label = str(types[0]).lower()
        for key in ("remote", "hybrid", "onsite"):
            if key in label:
                return key
    return ""
