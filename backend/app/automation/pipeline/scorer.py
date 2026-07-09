"""LLM-based job scoring against the user profile.

Uses the 5-dimension evaluation framework adapted from ai-job-search (MIT):
Technical Skills (30%), Experience (25%), Behavioral Fit (15%), Career
Alignment (30%), and Location (pass/fail veto). The LLM scores each dimension;
the weighted overall is computed deterministically in Python. See
docs/AUTOPILOT_PLAN.md section 8.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..profile import UserProfile
from . import llm

logger = logging.getLogger("jobpilot.autopilot.scorer")

# Dimension weights (must sum to 1.0). Location is a pass/fail veto, unweighted.
WEIGHTS = {
    "technical": 0.30,
    "experience": 0.25,
    "behavioral": 0.15,
    "career": 0.30,
}

_SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "technical": {"type": "integer"},
        "experience": {"type": "integer"},
        "behavioral": {"type": "integer"},
        "career": {"type": "integer"},
        "location_pass": {"type": "boolean"},
        "match_reasons": {"type": "array", "items": {"type": "string"}},
        "deal_breakers": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["technical", "experience", "behavioral", "career", "location_pass"],
}


@dataclass
class ScoreResult:
    job_id: str
    score: float = 0.0
    recommendation: str = "skip"
    match_reasons: list[str] = field(default_factory=list)
    deal_breakers: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    dimensions: dict = field(default_factory=dict)


def _build_system(profile: UserProfile) -> str:
    skills = ", ".join(profile.key_skills) or "(none listed)"
    langs = ", ".join(profile.languages) or "(none listed)"
    return (
        "You are a precise job-matching assistant. Score a job across four "
        "dimensions from 0 to 100, and judge location as pass/fail.\n"
        "- technical: how well required/preferred skills match the candidate\n"
        "- experience: how well work history aligns with the role\n"
        "- behavioral: culture/role fit with the candidate's profile\n"
        "- career: does this advance the candidate's direction and energize them\n"
        "- location_pass: false only for a hard location deal-breaker (e.g. "
        "on-site far away when the candidate needs remote)\n"
        "Be strict: only give 80+ when the candidate clearly meets core "
        "requirements. List deal_breakers (hard requirements NOT met) and "
        "missing_skills.\n\n"
        f"CANDIDATE PROFILE:\n"
        f"- Title: {profile.title}\n"
        f"- Years of experience: {profile.years_experience:.0f}\n"
        f"- Key skills: {skills}\n"
        f"- Languages: {langs}\n"
        f"- Location: {profile.location}\n"
        f"- Summary: {profile.summary[:400]}\n"
        "Respond ONLY with JSON matching the schema."
    )


def _build_prompt(job: dict) -> str:
    desc = (job.get("description") or "")[:1500]
    return (
        f"JOB:\n"
        f"- Title: {job.get('title', '')}\n"
        f"- Company: {job.get('company', '')}\n"
        f"- Location: {job.get('location', '')}\n"
        f"- Workplace: {job.get('workplace_type', '')}\n"
        f"- Description: {desc}\n\n"
        "Score technical, experience, behavioral, career (0-100 each), and "
        "location_pass (bool). Include match_reasons, deal_breakers, missing_skills."
    )


def compute_overall(dimensions: dict, location_pass: bool) -> float:
    """Weighted overall (0-100). A failed location veto caps the score at 39."""
    overall = sum(WEIGHTS[k] * float(dimensions.get(k, 0)) for k in WEIGHTS)
    if not location_pass:
        overall = min(overall, 39.0)
    return round(overall, 1)


def recommendation_for(score: float, location_pass: bool) -> str:
    """Map an overall score to a recommendation bucket."""
    if not location_pass:
        return "skip"
    if score >= 75:
        return "strong_match"
    if score >= 60:
        return "good"
    if score >= 45:
        return "partial"
    return "skip"


async def score_job(job: dict, profile: UserProfile) -> ScoreResult:
    """Score a single job with the 5-dimension framework. Skips on LLM failure."""
    job_id = job.get("job_id", "")
    try:
        data = await llm.generate_json(
            prompt=_build_prompt(job),
            system=_build_system(profile),
            schema=_SCORE_SCHEMA,
        )
    except llm.LLMError as exc:
        logger.warning("Scoring failed for %s: %s", job_id, exc)
        return ScoreResult(job_id=job_id, score=0.0, recommendation="skip")

    dims = {
        "technical": _clamp(data.get("technical")),
        "experience": _clamp(data.get("experience")),
        "behavioral": _clamp(data.get("behavioral")),
        "career": _clamp(data.get("career")),
    }
    location_pass = bool(data.get("location_pass", True))
    overall = compute_overall(dims, location_pass)
    dims["location_pass"] = location_pass

    return ScoreResult(
        job_id=job_id,
        score=overall,
        recommendation=recommendation_for(overall, location_pass),
        match_reasons=_as_str_list(data.get("match_reasons")),
        deal_breakers=_as_str_list(data.get("deal_breakers")),
        missing_skills=_as_str_list(data.get("missing_skills")),
        dimensions=dims,
    )


def _clamp(value) -> float:
    try:
        return float(max(0, min(100, int(value))))
    except (ValueError, TypeError):
        return 0.0


def _as_str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []
