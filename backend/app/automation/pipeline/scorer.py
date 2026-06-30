"""LLM-based job scoring against the user profile.

Produces a structured score (0-100) with reasons, deal-breakers and missing
skills. Uses deterministic JSON output (temperature 0) and a compressed prompt
that only includes the fields that matter, per docs/AUTOPILOT_PLAN.md section 8.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..profile import UserProfile
from . import llm

logger = logging.getLogger("jobpilot.autopilot.scorer")

_SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "recommendation": {
            "type": "string",
            "enum": ["strong_match", "good", "partial", "skip"],
        },
        "match_reasons": {"type": "array", "items": {"type": "string"}},
        "deal_breakers": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "recommendation"],
}


@dataclass
class ScoreResult:
    job_id: str
    score: float = 0.0
    recommendation: str = "skip"
    match_reasons: list[str] = field(default_factory=list)
    deal_breakers: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)


def _build_system(profile: UserProfile) -> str:
    skills = ", ".join(profile.key_skills) or "(none listed)"
    langs = ", ".join(profile.languages) or "(none listed)"
    return (
        "You are a precise job-matching assistant. Score how well a job fits the "
        "candidate from 0 to 100. Be strict: only give 80+ when the candidate "
        "clearly meets the core requirements. Identify deal-breakers (hard "
        "requirements the candidate does NOT meet) and missing skills.\n\n"
        f"CANDIDATE PROFILE:\n"
        f"- Title: {profile.title}\n"
        f"- Years of experience: {profile.years_experience:.0f}\n"
        f"- Key skills: {skills}\n"
        f"- Languages: {langs}\n"
        f"- Location: {profile.location}\n"
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
        "Score this job for the candidate. Return JSON with: score (0-100), "
        "recommendation (strong_match/good/partial/skip), match_reasons[], "
        "deal_breakers[], missing_skills[]."
    )


async def score_job(job: dict, profile: UserProfile) -> ScoreResult:
    """Score a single job. Returns a skip result on LLM failure."""
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

    return ScoreResult(
        job_id=job_id,
        score=_clamp_score(data.get("score", 0)),
        recommendation=str(data.get("recommendation", "skip")),
        match_reasons=_as_str_list(data.get("match_reasons")),
        deal_breakers=_as_str_list(data.get("deal_breakers")),
        missing_skills=_as_str_list(data.get("missing_skills")),
    )


def _clamp_score(value) -> float:
    try:
        return float(max(0, min(100, int(value))))
    except (ValueError, TypeError):
        return 0.0


def _as_str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []
