"""User profile manager - stores personal info for applications."""

import json
import logging
import os
import tempfile
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("jobpilot.profile")

PROFILE_FILE = "profile.json"


def get_profile_path() -> Path:
    """Get the path to the user profile file."""
    return Path(settings.data_dir) / PROFILE_FILE


def _default_profile() -> dict:
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


def get_profile() -> dict:
    """Load user profile. Returns the default (empty) profile if not set or
    if the file is corrupted (instead of raising and breaking every
    generation endpoint that depends on it).
    """
    path = get_profile_path()
    if not path.exists():
        return _default_profile()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("profile.json is corrupted or unreadable, using defaults: %s", exc)
        return _default_profile()


def save_profile(profile_data: dict) -> dict:
    """Save/update user profile.

    Writes atomically (temp file + rename) to avoid a corrupted profile.json
    if the process is interrupted mid-write.
    """
    path = get_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Merge with existing
    current = get_profile()
    current.update(profile_data)

    content = json.dumps(current, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".profile_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    return current
