"""Generate answers to custom application questions using the LLM."""

from __future__ import annotations

import logging

from ..pipeline import llm
from ..profile import UserProfile

logger = logging.getLogger("jobpilot.autopilot.answers")


async def answer_text_question(
    question: str,
    profile: UserProfile,
    job_title: str = "",
    company: str = "",
    cv_text: str = "",
    max_words: int = 150,
) -> str:
    """Generate a concise, contextual answer to a free-text question."""
    system = (
        "You are helping a job candidate answer an application question. Write a "
        "concise, specific, first-person answer grounded in the candidate's real "
        f"experience. Maximum {max_words} words. No preamble, just the answer."
    )
    prompt = (
        f"CANDIDATE: {profile.name}, {profile.title}, "
        f"{profile.years_experience:.0f} years, skills: {', '.join(profile.key_skills)}\n"
        f"JOB: {job_title} at {company}\n"
        f"CV EXCERPT: {cv_text[:1200]}\n\n"
        f"QUESTION: {question}\n\nAnswer:"
    )
    try:
        text = await llm.generate_text(prompt=prompt, system=system, temperature=0.6)
        return text.strip()
    except llm.LLMError as exc:
        logger.warning("Answer generation failed: %s", exc)
        return ""


async def choose_option(
    question: str,
    options: list[str],
    profile: UserProfile,
    job_title: str = "",
) -> str:
    """Pick the best option for a multiple-choice question. Returns the option text."""
    if not options:
        return ""
    if len(options) == 1:
        return options[0]

    numbered = "\n".join(f"{i}. {opt}" for i, opt in enumerate(options))
    schema = {
        "type": "object",
        "properties": {"index": {"type": "integer"}},
        "required": ["index"],
    }
    prompt = (
        f"CANDIDATE: {profile.title}, {profile.years_experience:.0f} years experience, "
        f"skills: {', '.join(profile.key_skills)}\n"
        f"JOB: {job_title}\n\n"
        f"QUESTION: {question}\nOPTIONS:\n{numbered}\n\n"
        "Choose the single best option for this candidate. Return JSON {index}."
    )
    try:
        data = await llm.generate_json(prompt=prompt, schema=schema)
        idx = int(data.get("index", 0))
        if 0 <= idx < len(options):
            return options[idx]
    except (llm.LLMError, ValueError, TypeError) as exc:
        logger.info("Option choice failed: %s", exc)
    return options[0]
