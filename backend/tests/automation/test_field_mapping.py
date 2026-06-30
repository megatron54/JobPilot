"""Tests for ATS detection and profile->field mapping (pure logic)."""

from __future__ import annotations

from app.automation.executor.field_mapping import detect_ats, value_for_field
from app.automation.profile import UserProfile


def test_detect_ats_greenhouse() -> None:
    assert detect_ats("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"
    assert detect_ats("https://job-boards.greenhouse.io/acme/jobs/1") == "greenhouse"


def test_detect_ats_lever() -> None:
    assert detect_ats("https://jobs.lever.co/acme/abc-123") == "lever"


def test_detect_ats_workday() -> None:
    assert detect_ats("https://acme.wd5.myworkdayjobs.com/careers/job/1") == "workday"


def test_detect_ats_smartrecruiters() -> None:
    assert detect_ats("https://jobs.smartrecruiters.com/acme/123") == "smartrecruiters"


def test_detect_ats_generic_fallback() -> None:
    assert detect_ats("https://careers.example.com/apply/1") == "generic"
    assert detect_ats("") == "generic"


def _profile() -> UserProfile:
    return UserProfile(
        name="Ada Lovelace",
        email="ada@example.com",
        phone="+34 600 000 000",
        linkedin_url="https://linkedin.com/in/ada",
        location="Madrid, Spain",
        title="Senior Engineer",
        years_experience=8,
        key_skills=["Python", "Rust"],
    )


def test_value_for_field_basic() -> None:
    p = _profile()
    assert value_for_field("first_name", p) == "Ada"
    assert value_for_field("last_name", p) == "Lovelace"
    assert value_for_field("full_name", p) == "Ada Lovelace"
    assert value_for_field("email", p) == "ada@example.com"
    assert value_for_field("phone", p) == "+34 600 000 000"
    assert value_for_field("linkedin_url", p) == "https://linkedin.com/in/ada"
    assert value_for_field("city", p) == "Madrid"
    assert value_for_field("current_title", p) == "Senior Engineer"
    assert value_for_field("experience_years", p) == "8"


def test_value_for_field_single_name() -> None:
    p = UserProfile(name="Cher")
    assert value_for_field("first_name", p) == "Cher"
    assert value_for_field("last_name", p) == ""


def test_value_for_field_extra_values() -> None:
    p = _profile()
    extra = {"salary_expectation": "70000", "work_authorization": "EU citizen"}
    assert value_for_field("salary_expectation", p, extra) == "70000"
    assert value_for_field("work_authorization", p, extra) == "EU citizen"


def test_value_for_field_unknown_is_empty() -> None:
    assert value_for_field("custom_question", _profile()) == ""
    assert value_for_field("unknown", _profile()) == ""
