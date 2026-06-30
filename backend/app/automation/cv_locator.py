"""Locate the user's CV file for uploads during applications."""

from __future__ import annotations

from pathlib import Path

from .config import settings

_CV_EXTENSIONS = (".pdf", ".docx", ".doc")


def find_cv_path() -> str | None:
    """Return the path to the most recent CV in data/cvs, or None.

    Prefers PDF (best ATS compatibility), then DOCX. Ignores the extracted
    .txt sidecar files.
    """
    cv_dir = Path(settings.data_dir).resolve() / "cvs"
    if not cv_dir.is_dir():
        return None

    candidates = [
        p for p in cv_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _CV_EXTENSIONS
    ]
    if not candidates:
        return None

    # Prefer PDF, then most recently modified.
    candidates.sort(key=lambda p: (p.suffix.lower() != ".pdf", -p.stat().st_mtime))
    return str(candidates[0])


def read_cv_text() -> str:
    """Return extracted CV text from the .txt sidecar if present."""
    cv_dir = Path(settings.data_dir).resolve() / "cvs"
    if not cv_dir.is_dir():
        return ""
    txts = sorted(
        cv_dir.glob("*.txt"), key=lambda p: -p.stat().st_mtime
    )
    if not txts:
        return ""
    try:
        return txts[0].read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
