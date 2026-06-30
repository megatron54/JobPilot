"""Load the user profile saved by the main app (profile.json)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from .config import settings

logger = logging.getLogger("jobpilot.autopilot.profile")


class UserProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    location: str = ""
    title: str = ""
    summary: str = ""
    key_skills: list[str] = Field(default_factory=list)
    years_experience: float = 0.0
    languages: list[str] = Field(default_factory=list)
    preferred_language: str = "es"
    tone: str = "professional"

    @property
    def skills_lower(self) -> set[str]:
        return {s.strip().lower() for s in self.key_skills if s.strip()}

    @property
    def languages_lower(self) -> set[str]:
        return {lang.strip().lower() for lang in self.languages if lang.strip()}


def load_profile() -> UserProfile:
    """Load profile.json from the data directory; empty profile if missing."""
    path = Path(settings.data_dir).resolve() / "profile.json"
    if not path.exists():
        logger.info("No profile.json found at %s", path)
        return UserProfile()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return UserProfile(**data)
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("Failed to load profile: %s", exc)
        return UserProfile()
