"""Tests for the discovery orchestrator (guest default + voyager path)."""

from __future__ import annotations

import pytest

from app.automation import discovery as discovery_mod
from app.automation.database import Database
from app.automation.jobs_repository import JobsRepository
from app.automation.linkedin.guest import GuestJobCard, GuestJobDetail
from app.automation.linkedin.search import JobStub
from app.automation.models import SearchCriteria
from app.automation.session import LinkedInSession

pytestmark = pytest.mark.asyncio


class FakeVoyagerClient:
    """Async-context-manager stand-in for LinkedInClient."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


# --- Guest path (default) ----------------------------------------------


async def test_guest_discovery_dedupes_and_persists(db: Database, monkeypatch) -> None:
    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="existing", title="Old", company="X"))

    cards = [
        GuestJobCard(id="existing", title="Old", company="X"),
        GuestJobCard(id="new1", title="New 1", company="Y", location="Madrid"),
        GuestJobCard(id="new2", title="New 2", company="Z", location="Remote"),
    ]

    async def fake_search_guest(keywords, location, jobage_days=7, remote="", page=1):
        return cards if page == 1 else []

    async def fake_guest_detail(job_id):
        return GuestJobDetail(id=job_id, description="desc", apply_url="https://x/apply")

    monkeypatch.setattr(discovery_mod, "search_guest", fake_search_guest)
    monkeypatch.setattr(discovery_mod, "fetch_guest_detail", fake_guest_detail)

    session = LinkedInSession()  # no session needed for guest
    result = await discovery_mod.discover(
        db, session, SearchCriteria(keywords=["dev"]), max_jobs=50, source="guest"
    )

    assert result.fetched == 3
    assert result.new == 2
    assert result.detailed == 2
    assert result.source_used == "guest"
    assert await repo.exists("new1")
    assert await repo.exists("new2")


async def test_guest_discovery_no_session_required(db: Database, monkeypatch) -> None:
    async def fake_search_guest(keywords, location, jobage_days=7, remote="", page=1):
        return [GuestJobCard(id="j1", title="Dev", company="X")] if page == 1 else []

    async def fake_guest_detail(job_id):
        return GuestJobDetail(id=job_id, description="d")

    monkeypatch.setattr(discovery_mod, "search_guest", fake_search_guest)
    monkeypatch.setattr(discovery_mod, "fetch_guest_detail", fake_guest_detail)

    result = await discovery_mod.discover(
        db, LinkedInSession(), SearchCriteria(keywords=["x"]), max_jobs=10, source="guest"
    )
    assert result.new == 1


# --- Voyager path -------------------------------------------------------


async def test_voyager_discovery(db: Database, monkeypatch) -> None:
    session = LinkedInSession()
    session.set_cookies("tok", "ajax:1")

    page = [
        JobStub(job_id="v1", title="V1", company="A"),
        JobStub(job_id="v2", title="V2", company="B"),
    ]

    async def fake_search(client, criteria, start=0, count=25):
        return page if start == 0 else []

    async def fake_details(client, job_id):
        from app.automation.linkedin.details import JobDetails

        return JobDetails(job_id=job_id, description="desc", apply_method="easy_apply")

    monkeypatch.setattr(discovery_mod, "search_jobs", fake_search)
    monkeypatch.setattr(discovery_mod, "fetch_job_details", fake_details)
    monkeypatch.setattr(discovery_mod, "LinkedInClient", lambda *_a, **_k: FakeVoyagerClient())

    result = await discovery_mod.discover(
        db, session, SearchCriteria(keywords=["dev"]), max_jobs=50, source="voyager"
    )
    assert result.fetched == 2
    assert result.new == 2
    assert result.detailed == 2


async def test_voyager_falls_back_to_guest_on_session_expiry(db: Database, monkeypatch) -> None:
    from app.automation.linkedin.search import search_jobs as real_search  # noqa: F401

    session = LinkedInSession()
    session.set_cookies("tok", "ajax:1")

    async def failing_search(client, criteria, start=0, count=25):
        from app.automation.linkedin.client import SessionExpiredError

        raise SessionExpiredError("expired")

    async def fake_search_guest(keywords, location, jobage_days=7, remote="", page=1):
        return [GuestJobCard(id="g1", title="Guest", company="X")] if page == 1 else []

    async def fake_guest_detail(job_id):
        return GuestJobDetail(id=job_id, description="d")

    monkeypatch.setattr(discovery_mod, "search_jobs", failing_search)
    monkeypatch.setattr(discovery_mod, "LinkedInClient", lambda *_a, **_k: FakeVoyagerClient())
    monkeypatch.setattr(discovery_mod, "search_guest", fake_search_guest)
    monkeypatch.setattr(discovery_mod, "fetch_guest_detail", fake_guest_detail)

    result = await discovery_mod.discover(
        db, session, SearchCriteria(keywords=["x"]), max_jobs=10, source="voyager"
    )
    # Voyager failed -> fell back to guest, found g1
    assert "fallback" in result.source_used
    assert result.new == 1
    assert await JobsRepository(db).exists("g1")
