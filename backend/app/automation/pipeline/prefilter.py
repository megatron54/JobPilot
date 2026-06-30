"""Rule-based pre-filtering to eliminate non-matching jobs before LLM scoring.

These are fast set/string/regex operations (sub-millisecond per job) that
remove ~60-70% of jobs so the LLM only scores genuine candidates. See
docs/AUTOPILOT_PLAN.md section 6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import SearchCriteria
from ..profile import UserProfile

_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:years|años|yrs)", re.IGNORECASE)


@dataclass
class FilterDecision:
    keep: bool
    reason: str = ""


def prefilter_job(
    job: dict,
    profile: UserProfile,
    criteria: SearchCriteria,
) -> FilterDecision:
    """Decide whether a job survives pre-filtering.

    `job` is a dict row from discovered_jobs (title, company, description,
    workplace_type, requirements, etc.).
    """
    title = (job.get("title") or "").lower()
    company = (job.get("company") or "").lower()
    description = (job.get("description") or "").lower()
    workplace = (job.get("workplace_type") or "").lower()
    blob = f"{title} {description}"

    # 1. Company blacklist
    for excluded in criteria.excluded_companies:
        if excluded.strip() and excluded.strip().lower() in company:
            return FilterDecision(False, f"excluded company: {excluded}")

    # 2. Excluded keywords
    for kw in criteria.excluded_keywords:
        if kw.strip() and kw.strip().lower() in blob:
            return FilterDecision(False, f"excluded keyword: {kw}")

    # 3. Required keywords (all must be present)
    for kw in criteria.required_keywords:
        if kw.strip() and kw.strip().lower() not in blob:
            return FilterDecision(False, f"missing required keyword: {kw}")

    # 4. Workplace preference mismatch
    decision = _check_workplace(workplace, criteria)
    if not decision.keep:
        return decision

    # 5. Experience mismatch (job requires far more than the user has)
    decision = _check_experience(blob, profile)
    if not decision.keep:
        return decision

    return FilterDecision(True)


def _check_workplace(workplace: str, criteria: SearchCriteria) -> FilterDecision:
    # Only enforce if the user expressed a preference and the job is explicit.
    wants_any = criteria.remote or criteria.hybrid or criteria.onsite
    if not wants_any or not workplace:
        return FilterDecision(True)

    allowed = set()
    if criteria.remote:
        allowed.add("remote")
    if criteria.hybrid:
        allowed.add("hybrid")
    if criteria.onsite:
        allowed.add("onsite")

    if workplace not in allowed:
        return FilterDecision(False, f"workplace {workplace} not in preference")
    return FilterDecision(True)


def _check_experience(blob: str, profile: UserProfile) -> FilterDecision:
    if profile.years_experience <= 0:
        return FilterDecision(True)
    matches = _YEARS_RE.findall(blob)
    if not matches:
        return FilterDecision(True)
    required = max(int(m) for m in matches)
    # Reject only when the gap is large (job wants >1.5x the user's experience).
    if required > profile.years_experience * 1.5 and required - profile.years_experience >= 3:
        return FilterDecision(
            False, f"requires ~{required}y vs profile {profile.years_experience:.0f}y"
        )
    return FilterDecision(True)


def skill_overlap(job: dict, profile: UserProfile) -> float:
    """Rough fraction of the user's skills mentioned in the job text (0-1)."""
    skills = profile.skills_lower
    if not skills:
        return 0.0
    blob = f"{job.get('title', '')} {job.get('description', '')}".lower()
    hits = sum(1 for s in skills if s in blob)
    return hits / len(skills)
