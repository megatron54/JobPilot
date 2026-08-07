"""Tests for app/services/profile_manager.py: default fallback, corruption
recovery, and atomic writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.services.profile_manager import get_profile, get_profile_path, save_profile


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    return tmp_path


def test_get_profile_returns_defaults_when_missing():
    profile = get_profile()
    assert profile["name"] == ""
    assert profile["preferred_language"] == "es"


def test_save_and_reload_profile_roundtrip():
    save_profile({"name": "Ada Lovelace", "email": "ada@example.com"})
    profile = get_profile()
    assert profile["name"] == "Ada Lovelace"
    assert profile["email"] == "ada@example.com"


def test_save_profile_merges_with_existing_fields():
    save_profile({"name": "Ada"})
    save_profile({"email": "ada@example.com"})
    profile = get_profile()
    assert profile["name"] == "Ada"
    assert profile["email"] == "ada@example.com"


def test_corrupted_profile_json_falls_back_to_defaults(isolated_data_dir: Path):
    get_profile_path().write_text("{not valid json", encoding="utf-8")
    profile = get_profile()
    assert profile["name"] == ""


def test_save_profile_writes_atomically_no_leftover_temp_files(isolated_data_dir: Path):
    save_profile({"name": "Grace Hopper"})
    leftovers = list(isolated_data_dir.glob(".profile_*"))
    assert leftovers == []
    assert get_profile_path().exists()
