"""User profile manager - stores personal info for applications."""

import json
from pathlib import Path

from app.core.config import settings


PROFILE_FILE = "profile.json"


def get_profile_path() -> Path:
    """Get the path to the user profile file."""
    return Path(settings.data_dir) / PROFILE_FILE


def get_profile() -> dict:
    """Load user profile. Returns empty dict if not set."""
    path = get_profile_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "name": "",
        "email": "",
        "phone": "",
        "linkedin_url": "",
        "location": "",
        "title": "",
        "summary": "",
        "key_skills": [],
        "years_experience": 0,
        "education": [],
        "languages": [],
        "preferred_language": "es",
        "tone": "professional",  # professional, friendly, formal
    }


def save_profile(profile_data: dict) -> dict:
    """Save/update user profile."""
    path = get_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Merge with existing
    current = get_profile()
    current.update(profile_data)

    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current
