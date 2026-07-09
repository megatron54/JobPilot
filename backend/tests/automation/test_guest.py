"""Tests for the LinkedIn guest (unauthenticated) search client."""

from __future__ import annotations

from app.automation.linkedin import guest


# --- URL building -------------------------------------------------------


def test_jobage_to_tpr() -> None:
    assert guest.jobage_to_tpr(7) == "r604800"
    assert guest.jobage_to_tpr(0) == ""
    assert guest.jobage_to_tpr(9999) == ""


def test_work_type_flag() -> None:
    assert guest.work_type_flag("remote") == "2"
    assert guest.work_type_flag("hybrid") == "3"
    assert guest.work_type_flag("onsite") == "1"
    assert guest.work_type_flag("on-site") == "1"
    assert guest.work_type_flag("") == ""


def test_build_search_url() -> None:
    url = guest.build_search_url("data engineer", "Berlin, Germany", 7, "remote", 1)
    assert url.startswith(guest.SEARCH_URL)
    assert "keywords=data" in url or "keywords=data%20engineer" in url or "keywords=data+engineer" in url
    assert "f_TPR=r604800" in url
    assert "f_WT=2" in url
    assert "start=0" in url


def test_build_search_url_pagination() -> None:
    url = guest.build_search_url("dev", "Remote", 30, "", 3)
    assert "start=20" in url  # (page-1)*10


# --- Job card parsing ---------------------------------------------------

_SEARCH_HTML = """
<ul>
<li>
  <div class="base-card" data-entity-urn="urn:li:jobPosting:3811111111">
    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/react-dev-3811111111?trk=x">link</a>
    <h3 class="base-search-card__title">Senior React Developer</h3>
    <h4 class="base-search-card__subtitle"><a href="https://www.linkedin.com/company/acme?x=1">Acme Corp</a></h4>
    <span class="job-search-card__location">Madrid, Spain</span>
    <time class="job-search-card__listdate" datetime="2026-06-20">June 20</time>
  </div>
</li>
<li>
  <div class="base-card" data-entity-urn="urn:li:jobPosting:3822222222">
    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/3822222222">link</a>
    <h3 class="base-search-card__title">Backend Engineer</h3>
    <h4 class="base-search-card__subtitle">Globex</h4>
    <span class="job-search-card__location">Remote</span>
  </div>
</li>
</ul>
"""


def test_parse_job_cards() -> None:
    cards = guest.parse_job_cards(_SEARCH_HTML)
    assert len(cards) == 2

    a = cards[0]
    assert a.id == "3811111111"
    assert a.title == "Senior React Developer"
    assert a.company == "Acme Corp"
    assert a.company_url == "https://www.linkedin.com/company/acme"
    assert a.location == "Madrid, Spain"
    assert a.date == "2026-06-20"
    assert "?" not in a.url  # query stripped

    b = cards[1]
    assert b.id == "3822222222"
    assert b.company == "Globex"
    assert b.location == "Remote"


def test_parse_job_cards_empty() -> None:
    assert guest.parse_job_cards("<html>nothing</html>") == []


def test_parse_job_cards_decodes_entities() -> None:
    html = (
        '<div data-entity-urn="urn:li:jobPosting:999">'
        '<h3 class="base-search-card__title">R&amp;D Engineer</h3>'
        '<h4 class="base-search-card__subtitle">AT&amp;T</h4></div>'
    )
    cards = guest.parse_job_cards(html)
    assert cards[0].title == "R&D Engineer"
    assert cards[0].company == "AT&T"


# --- Job detail parsing -------------------------------------------------

_DETAIL_HTML = """
<h1 class="top-card-layout__title">Data Scientist</h1>
<a class="topcard__org-name-link" href="https://www.linkedin.com/company/initech?x=1">Initech</a>
<span class="topcard__flavor topcard__flavor--bullet">Barcelona, Spain</span>
<div class="show-more-less-html__markup">
  <p>We need Python and ML.</p><ul><li>scikit-learn</li><li>pandas</li></ul>
</div>
<h3 class="description__job-criteria-subheader">Seniority level</h3>
<span class="description__job-criteria-text">Mid-Senior level</span>
<h3 class="description__job-criteria-subheader">Employment type</h3>
<span class="description__job-criteria-text">Full-time</span>
"""


def test_parse_job_detail() -> None:
    d = guest.parse_job_detail(_DETAIL_HTML, "12345")
    assert d.id == "12345"
    assert d.title == "Data Scientist"
    assert d.company == "Initech"
    assert d.location == "Barcelona, Spain"
    assert "Python and ML" in d.description
    assert "scikit-learn" in d.description
    assert d.seniority == "Mid-Senior level"
    assert d.employment_type == "Full-time"
