"""Regression tests: CV read/upload must never escape the configured cv_dir."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.services.cv_parser import get_cv_content


@pytest.fixture(autouse=True)
def isolated_cv_dir(tmp_path: Path, monkeypatch):
    cv_dir = tmp_path / "cvs"
    cv_dir.mkdir()
    monkeypatch.setattr(settings, "cv_dir", str(cv_dir))
    return cv_dir


def test_get_cv_content_reads_a_real_cv(isolated_cv_dir: Path):
    (isolated_cv_dir / "resume.txt").write_text("Experienced engineer.", encoding="utf-8")
    assert get_cv_content("resume.txt") == "Experienced engineer."


def test_get_cv_content_blocks_path_traversal_to_sibling_file(tmp_path: Path, isolated_cv_dir: Path):
    # A secret file that lives *outside* the cv directory.
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        get_cv_content("../secret.txt")


def test_get_cv_content_blocks_absolute_path_escape(tmp_path: Path, isolated_cv_dir: Path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        get_cv_content(str(secret))


def test_get_cv_content_missing_file_raises_not_found(isolated_cv_dir: Path):
    with pytest.raises(FileNotFoundError):
        get_cv_content("does_not_exist.txt")
