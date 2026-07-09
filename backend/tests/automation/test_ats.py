"""Tests for ATS keyword coverage (pure matching logic)."""

from __future__ import annotations

import pytest

from app.automation.pipeline import ats
from app.automation.pipeline.ats import check_coverage
from app.automation.profile import UserProfile

pytestmark = pytest.mark.asyncio


def _profile() -> UserProfile:
    return UserProfile(
        title="Senior React Developer",
        key_skills=["React", "TypeScript", "Node.js"],
        summary="Built scalable web apps with GraphQL",
    )


def test_check_coverage_basic() -> None:
    cov = check_coverage(["React", "TypeScript", "Kubernetes"], _profile())
    assert "React" in cov.covered
    assert "TypeScript" in cov.covered
    assert "Kubernetes" in cov.missing
    assert cov.total == 3
    assert abs(cov.ratio - 2 / 3) < 0.01


def test_check_coverage_from_cv_text() -> None:
    cov = check_coverage(["Docker"], _profile(), cv_text="Deployed with Docker and CI/CD")
    assert "Docker" in cov.covered


def test_check_coverage_from_summary() -> None:
    cov = check_coverage(["GraphQL"], _profile())
    assert "GraphQL" in cov.covered


def test_check_coverage_word_boundary() -> None:
    # 'Java' must not match 'JavaScript'
    p = UserProfile(key_skills=["JavaScript"])
    cov = check_coverage(["Java"], p)
    assert "Java" in cov.missing


def test_check_coverage_dedups() -> None:
    cov = check_coverage(["React", "react", "REACT"], _profile())
    assert cov.total == 1


def test_check_coverage_handles_special_chars() -> None:
    p = UserProfile(key_skills=["C++", "C#", ".NET"])
    cov = check_coverage(["C++", "C#"], p)
    assert "C++" in cov.covered
    assert "C#" in cov.covered


def test_empty_keywords() -> None:
    cov = check_coverage([], _profile())
    assert cov.total == 0
    assert cov.ratio == 0.0


async def test_analyze_ats_uses_extraction(monkeypatch) -> None:
    async def fake_extract(job_title, description, max_keywords=15):
        return ["React", "Kubernetes"]

    monkeypatch.setattr(ats, "extract_keywords", fake_extract)
    cov = await ats.analyze_ats("Dev", "some description", _profile())
    assert "React" in cov.covered
    assert "Kubernetes" in cov.missing
