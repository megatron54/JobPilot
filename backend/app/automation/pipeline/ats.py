"""ATS keyword coverage analysis.

Extracts the key skills/keywords a posting emphasizes and measures how many the
candidate's profile + CV genuinely cover. Inspired by the ATS verification step
in ai-job-search (MIT). The coverage matching is a pure function (testable); the
keyword extraction uses the LLM.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ..profile import UserProfile
from . import llm

logger = logging.getLogger("jobpilot.autopilot.ats")

_KEYWORDS_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["keywords"],
}


@dataclass
class KeywordCoverage:
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.covered) + len(self.missing)

    @property
    def ratio(self) -> float:
        return len(self.covered) / self.total if self.total else 0.0


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9+#. ]", " ", text.lower())


def check_coverage(keywords: list[str], profile: UserProfile, cv_text: str = "") -> KeywordCoverage:
    """Match posting keywords against the candidate's skills + CV text.

    A keyword counts as covered when it appears (word-boundary, case-insensitive)
    in the profile skills or the CV text. Pure function - no LLM.
    """
    haystack = _normalize(
        " ".join(profile.key_skills) + " " + profile.title + " " + profile.summary + " " + cv_text
    )
    covered: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for kw in keywords:
        key = kw.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if _keyword_present(key, haystack):
            covered.append(kw.strip())
        else:
            missing.append(kw.strip())
    return KeywordCoverage(covered=covered, missing=missing)


def _keyword_present(keyword: str, haystack: str) -> bool:
    kw = _normalize(keyword).strip()
    if not kw:
        return False
    # Escape for regex; allow the keyword to appear as a standalone token/phrase.
    pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


async def extract_keywords(job_title: str, description: str, max_keywords: int = 15) -> list[str]:
    """Use the LLM to extract the posting's key required skills/technologies."""
    if not description.strip():
        return []
    prompt = (
        f"Extract the {max_keywords} most important required skills, technologies, "
        f"tools, and hard requirements from this job posting. Return concrete terms "
        f"(e.g. 'React', 'Kubernetes', 'SQL'), not soft phrases.\n\n"
        f"TITLE: {job_title}\nDESCRIPTION: {description[:2000]}\n\n"
        'Return JSON {"keywords": ["...", "..."]}.'
    )
    try:
        data = await llm.generate_json(prompt=prompt, schema=_KEYWORDS_SCHEMA)
        kws = data.get("keywords", [])
        return [str(k).strip() for k in kws if str(k).strip()][:max_keywords]
    except llm.LLMError as exc:
        logger.info("Keyword extraction failed: %s", exc)
        return []


async def analyze_ats(
    job_title: str, description: str, profile: UserProfile, cv_text: str = ""
) -> KeywordCoverage:
    """Full ATS pass: extract keywords then measure coverage."""
    keywords = await extract_keywords(job_title, description)
    return check_coverage(keywords, profile, cv_text)
