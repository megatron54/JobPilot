"""Tests for the rule-based pre-filter."""

from __future__ import annotations

from app.automation.models import SearchCriteria
from app.automation.pipeline.prefilter import prefilter_job, skill_overlap
from app.automation.profile import UserProfile


def _profile(**kw) -> UserProfile:
    base = dict(years_experience=5, key_skills=["React", "TypeScript", "Node"])
    base.update(kw)
    return UserProfile(**base)


def test_keeps_normal_job() -> None:
    job = {"title": "React Developer", "company": "Acme", "description": "React and Node"}
    decision = prefilter_job(job, _profile(), SearchCriteria(keywords=["React"]))
    assert decision.keep is True


def test_excludes_blacklisted_company() -> None:
    job = {"title": "Dev", "company": "EvilCorp", "description": "x"}
    criteria = SearchCriteria(keywords=["Dev"], excluded_companies=["EvilCorp"])
    decision = prefilter_job(job, _profile(), criteria)
    assert decision.keep is False
    assert "company" in decision.reason


def test_excludes_excluded_keyword() -> None:
    job = {"title": "Senior PHP Dev", "company": "X", "description": "PHP legacy"}
    criteria = SearchCriteria(keywords=["Dev"], excluded_keywords=["PHP"])
    decision = prefilter_job(job, _profile(), criteria)
    assert decision.keep is False


def test_requires_required_keyword() -> None:
    job = {"title": "Java Developer", "company": "X", "description": "Java only"}
    criteria = SearchCriteria(keywords=["Dev"], required_keywords=["React"])
    decision = prefilter_job(job, _profile(), criteria)
    assert decision.keep is False
    assert "required" in decision.reason


def test_workplace_mismatch() -> None:
    job = {"title": "Dev", "company": "X", "description": "y", "workplace_type": "onsite"}
    criteria = SearchCriteria(keywords=["Dev"], remote=True)
    decision = prefilter_job(job, _profile(), criteria)
    assert decision.keep is False


def test_experience_gap_rejected() -> None:
    job = {
        "title": "Principal Engineer",
        "company": "X",
        "description": "Requires 12 years of experience",
    }
    decision = prefilter_job(job, _profile(years_experience=3), SearchCriteria(keywords=["x"]))
    assert decision.keep is False


def test_experience_within_range_kept() -> None:
    job = {"title": "Dev", "company": "X", "description": "Requires 6 years experience"}
    decision = prefilter_job(job, _profile(years_experience=5), SearchCriteria(keywords=["x"]))
    assert decision.keep is True


def test_skill_overlap() -> None:
    job = {"title": "React Dev", "description": "We use React and TypeScript daily"}
    overlap = skill_overlap(job, _profile())
    assert overlap > 0.6  # 2 of 3 skills present
