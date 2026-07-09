"""Generate application content (cover letters, recruiter messages) for the queue.

Reuses the automation LLM client. Kept concise and grounded in the profile/CV.
Supports an optional drafter-reviewer refinement pass (adapted from the
drafter-reviewer workflow in ai-job-search, MIT) using two local LLM calls.
"""

from __future__ import annotations

import logging

from .pipeline import llm
from .profile import UserProfile
from .writing_style import STYLE_RULES

logger = logging.getLogger("jobpilot.autopilot.content")

_LANG_NAME = {"es": "Spanish", "en": "English", "fr": "French", "de": "German", "pt": "Portuguese"}


async def generate_cover_letter(
    profile: UserProfile,
    job_title: str,
    company: str,
    description: str = "",
    cv_text: str = "",
    emphasize_keywords: list[str] | None = None,
    refine: bool = False,
) -> str:
    lang = _LANG_NAME.get(profile.preferred_language, "Spanish")
    system = (
        f"You are an expert career writer. Write a concise, compelling cover letter in {lang}. "
        f"Tone: {profile.tone}. 3 short paragraphs. No placeholders, no '[brackets]'. "
        "Ground every claim in the candidate's real experience. Never fabricate skills.\n\n"
        + STYLE_RULES
    )
    kw_line = ""
    if emphasize_keywords:
        kw_line = (
            "\nNaturally emphasize these skills the candidate genuinely has and the role "
            f"values: {', '.join(emphasize_keywords[:8])}. Do not force keywords the "
            "candidate lacks."
        )
    prompt = (
        f"CANDIDATE: {profile.name}, {profile.title}, {profile.years_experience:.0f} years.\n"
        f"SKILLS: {', '.join(profile.key_skills)}\n"
        f"CV: {cv_text[:1500]}\n\n"
        f"JOB: {job_title} at {company}\n"
        f"DESCRIPTION: {description[:1200]}{kw_line}\n\n"
        "Write the cover letter now."
    )
    try:
        draft = (await llm.generate_text(prompt=prompt, system=system, temperature=0.6)).strip()
    except llm.LLMError as exc:
        logger.warning("Cover letter generation failed: %s", exc)
        return ""

    if refine and draft:
        return await refine_cover_letter(draft, job_title, company, description, lang)
    return draft


async def refine_cover_letter(
    draft: str, job_title: str, company: str, description: str, lang: str
) -> str:
    """Drafter-reviewer pass: critique the draft, then revise it (2 LLM calls)."""
    review_system = (
        "You are a strict cover-letter reviewer. Critique the draft in 3-5 bullet "
        "points: flag cliches and filler, generic/unsupported claims, weak or "
        "backward-looking framing, and missed alignment with the job. Be specific. "
        "Do NOT rewrite it - only critique."
    )
    review_prompt = (
        f"JOB: {job_title} at {company}\nPOSTING: {description[:800]}\n\n"
        f"DRAFT:\n{draft}\n\nList the critique bullets."
    )
    try:
        critique = (await llm.generate_text(
            prompt=review_prompt, system=review_system, temperature=0.3
        )).strip()
    except llm.LLMError:
        return draft  # reviewer failed; keep the draft

    revise_system = (
        f"You are an expert career writer. Revise the cover letter in {lang} to address "
        "the reviewer's critique. Keep it to 3 short paragraphs, grounded in real "
        "experience, forward-looking.\n\n" + STYLE_RULES
    )
    revise_prompt = (
        f"ORIGINAL DRAFT:\n{draft}\n\nREVIEWER CRITIQUE:\n{critique}\n\n"
        "Write the improved final cover letter (output only the letter)."
    )
    try:
        revised = (await llm.generate_text(
            prompt=revise_prompt, system=revise_system, temperature=0.6
        )).strip()
        return revised or draft
    except llm.LLMError:
        return draft


async def generate_recruiter_message(
    profile: UserProfile,
    job_title: str,
    company: str,
    recruiter_name: str = "",
    max_chars: int = 280,
) -> str:
    lang = _LANG_NAME.get(profile.preferred_language, "Spanish")
    greeting = f"to {recruiter_name}" if recruiter_name else "to the hiring team"
    system = (
        f"Write a short, warm LinkedIn connection note in {lang} {greeting}. "
        f"Tone: {profile.tone}. Under {max_chars} characters. Mention the role and one "
        "genuine reason for interest. No links, no markdown, first person. "
        "No cliches ('passionate about', 'great fit', 'leverage'). Be specific and human."
    )
    prompt = (
        f"CANDIDATE: {profile.name}, {profile.title}.\n"
        f"ROLE OF INTEREST: {job_title} at {company}.\n"
        "Write the note now."
    )
    try:
        text = (await llm.generate_text(prompt=prompt, system=system, temperature=0.7)).strip()
        return text[:max_chars]
    except llm.LLMError as exc:
        logger.warning("Recruiter message generation failed: %s", exc)
        return ""
