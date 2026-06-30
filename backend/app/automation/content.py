"""Generate application content (cover letters, recruiter messages) for the queue.

Reuses the automation LLM client. Kept concise and grounded in the profile/CV.
"""

from __future__ import annotations

import logging

from .pipeline import llm
from .profile import UserProfile

logger = logging.getLogger("jobpilot.autopilot.content")

_LANG_NAME = {"es": "Spanish", "en": "English", "fr": "French", "de": "German", "pt": "Portuguese"}


async def generate_cover_letter(
    profile: UserProfile,
    job_title: str,
    company: str,
    description: str = "",
    cv_text: str = "",
) -> str:
    lang = _LANG_NAME.get(profile.preferred_language, "Spanish")
    system = (
        f"You are an expert career writer. Write a concise, compelling cover letter in {lang}. "
        f"Tone: {profile.tone}. 3 short paragraphs. No placeholders, no '[brackets]'. "
        "Ground every claim in the candidate's real experience."
    )
    prompt = (
        f"CANDIDATE: {profile.name}, {profile.title}, {profile.years_experience:.0f} years.\n"
        f"SKILLS: {', '.join(profile.key_skills)}\n"
        f"CV: {cv_text[:1500]}\n\n"
        f"JOB: {job_title} at {company}\n"
        f"DESCRIPTION: {description[:1200]}\n\n"
        "Write the cover letter now."
    )
    try:
        return (await llm.generate_text(prompt=prompt, system=system, temperature=0.6)).strip()
    except llm.LLMError as exc:
        logger.warning("Cover letter generation failed: %s", exc)
        return ""


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
        "genuine reason for interest. No links, no markdown, first person."
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
