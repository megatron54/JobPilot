"""Tests for Voyager response parsing and search/detail logic."""

from __future__ import annotations

from app.automation.linkedin import details, parsing, search
from app.automation.models import SearchCriteria


# --- parsing helpers ----------------------------------------------------


def test_job_id_from_urn() -> None:
    assert parsing.job_id_from_urn("urn:li:fs_jobPosting:1234567890") == "1234567890"
    assert parsing.job_id_from_urn("") == ""


def test_text_of_handles_attributed_text() -> None:
    assert parsing.text_of({"text": "Hello"}) == "Hello"
    assert parsing.text_of("Plain") == "Plain"
    assert parsing.text_of(None) == ""


def test_build_index() -> None:
    payload = {
        "included": [
            {"entityUrn": "urn:a", "name": "A"},
            {"entityUrn": "urn:b", "name": "B"},
            {"no_urn": True},
        ]
    }
    index = parsing.build_index(payload)
    assert set(index.keys()) == {"urn:a", "urn:b"}
    assert index["urn:a"]["name"] == "A"


# --- search params ------------------------------------------------------


def test_build_search_params_basic() -> None:
    criteria = SearchCriteria(keywords=["React", "TypeScript"], remote=True)
    params = search.build_search_params(criteria, start=0, count=25)
    assert params["query"] == "React TypeScript"
    assert params["count"] == 25
    assert "workplaceType->2" in params["filters"]


def test_build_search_params_experience_and_time() -> None:
    criteria = SearchCriteria(
        keywords=["Dev"], experience_levels=["3", "4"], posted_within_hours=24
    )
    params = search.build_search_params(criteria)
    assert "experience->3|4" in params["filters"]
    assert "timePostedRange->r86400" in params["filters"]


def test_count_capped_at_25() -> None:
    params = search.build_search_params(SearchCriteria(keywords=["x"]), count=100)
    assert params["count"] == 25


# --- search stub parsing ------------------------------------------------


def test_parse_job_stubs() -> None:
    payload = {
        "included": [
            {
                "$type": "com.linkedin.voyager.jobs.JobPosting",
                "entityUrn": "urn:li:fs_jobPosting:111",
                "title": "Senior React Developer",
                "formattedLocation": "Madrid, Spain",
                "workRemoteAllowed": True,
                "companyDetails": {"company": "urn:li:fs_baseCompany:55"},
            },
            {
                "$type": "com.linkedin.voyager.jobs.BaseCompany",
                "entityUrn": "urn:li:fs_baseCompany:55",
                "name": "TechCorp",
            },
        ]
    }
    stubs = search.parse_job_stubs(payload)
    assert len(stubs) == 1
    assert stubs[0].job_id == "111"
    assert stubs[0].title == "Senior React Developer"
    assert stubs[0].company == "TechCorp"
    assert stubs[0].company_id == "55"
    assert stubs[0].workplace_type == "remote"


def test_parse_job_stubs_dedupes() -> None:
    payload = {
        "included": [
            {
                "$type": "JobPosting",
                "entityUrn": "urn:li:fs_jobPosting:1",
                "title": "A",
            },
            {
                "$type": "JobPosting",
                "entityUrn": "urn:li:fs_jobPosting:1",
                "title": "A dup",
            },
        ]
    }
    stubs = search.parse_job_stubs(payload)
    assert len(stubs) == 1


# --- detail parsing -----------------------------------------------------


def test_parse_apply_method_easy() -> None:
    data = {"applyMethod": {"com.linkedin.voyager.jobs.ComplexOnsiteApply": {}}}
    method, url = details._parse_apply_method(data)
    assert method == "easy_apply"
    assert url == ""


def test_parse_apply_method_external() -> None:
    data = {
        "applyMethod": {
            "com.linkedin.voyager.jobs.OffsiteApply": {
                "companyApplyUrl": "https://careers.example.com/job/1"
            }
        }
    }
    method, url = details._parse_apply_method(data)
    assert method == "external"
    assert url == "https://careers.example.com/job/1"


def test_parse_job_details_full() -> None:
    payload = {
        "data": {
            "title": "Backend Engineer",
            "formattedLocation": "Remote",
            "description": {"text": "We need Python skills"},
            "applyMethod": {"com.linkedin.voyager.jobs.ComplexOnsiteApply": {}},
            "workRemoteAllowed": True,
            "applies": 42,
        },
        "included": [
            {"$type": "com.linkedin.voyager.organization.Company", "name": "Acme"},
        ],
    }
    d = details.parse_job_details("999", payload)
    assert d.title == "Backend Engineer"
    assert d.company == "Acme"
    assert d.description == "We need Python skills"
    assert d.apply_method == "easy_apply"
    assert d.workplace_type == "remote"
    assert d.num_applicants == 42
