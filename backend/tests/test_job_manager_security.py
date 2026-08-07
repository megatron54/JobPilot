"""Regression tests: job save/get/delete must never escape jobs_dir, and
company/position must not be usable to write outside it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.job_manager import delete_job, get_job, save_job_offer


@pytest.fixture(autouse=True)
def isolated_jobs_dir(tmp_path: Path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr(settings, "jobs_dir", str(jobs_dir))
    return jobs_dir


def test_save_job_offer_writes_inside_jobs_dir(isolated_jobs_dir: Path):
    saved = save_job_offer({"company": "Acme Corp", "position": "Backend Engineer"})
    files = list(isolated_jobs_dir.glob("*.json"))
    assert len(files) == 1
    assert files[0].parent == isolated_jobs_dir
    assert saved["id"] == files[0].stem


def test_save_job_offer_sanitizes_malicious_company_name(tmp_path: Path, isolated_jobs_dir: Path):
    """A crafted `company`/`position` must not let the resulting filename
    escape jobs_dir (e.g. company="../../evil")."""
    saved = save_job_offer({"company": "../../evil", "position": "../../../also_evil"})
    files = list(isolated_jobs_dir.glob("*.json"))
    assert len(files) == 1
    assert files[0].parent == isolated_jobs_dir
    # Nothing was written outside the tmp tree either.
    assert not (tmp_path / "evil.json").exists()


def test_get_job_blocks_path_traversal(tmp_path: Path, isolated_jobs_dir: Path):
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"secret": True}), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        get_job("../secret")


def test_delete_job_blocks_path_traversal(tmp_path: Path, isolated_jobs_dir: Path):
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"secret": True}), encoding="utf-8")

    # Must not delete the file outside jobs_dir, and must report "not found".
    assert delete_job("../secret") is False
    assert secret.exists()


def test_get_job_roundtrip(isolated_jobs_dir: Path):
    saved = save_job_offer({"company": "Acme", "position": "Engineer", "raw_description": "desc"})
    fetched = get_job(saved["id"])
    assert fetched["company"] == "Acme"


def test_delete_job_roundtrip(isolated_jobs_dir: Path):
    saved = save_job_offer({"company": "Acme", "position": "Engineer"})
    assert delete_job(saved["id"]) is True
    with pytest.raises(FileNotFoundError):
        get_job(saved["id"])
