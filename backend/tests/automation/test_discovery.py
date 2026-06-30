"""Tests for the discovery orchestrator using a mocked LinkedIn client."""

from __future__ import annotations

import pytest

from app.automation import discovery as discovery_mod
from app.automation.database import Database
from app.automation.jobs_repository import JobsRepository
from app.automation.linkedin.search import JobStub
from app.automation.models import SearchCriteria
from app.automation.session import LinkedInSession

pytestmark = pytest.mark.asyncio


class FakeClient:
    """Stand-in for LinkedInClient used as an async context manager."""

    def __init__(self, pages: list[list[JobStub]]) -> None:
        self._pages = pages
        self._calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_discover_dedupes_and_persists(db: Database, monkeypatch) -> None:
    session = LinkedInSession()
    session.set_cookies("tok", "ajax:1")

    # Pre-seed one job so dedup excludes it.
    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="existing", title="Old", company="X"))

    page = [
        JobStub(job_id="existing", title="Old", company="X"),
        JobStub(job_id="new1", title="New 1", company="Y"),
        JobStub(job_id="new2", title="New 2", company="Z"),
    ]

    async def fake_search(client, criteria, start=0, count=25):
        return page if start == 0 else []

    async def fake_details(client, job_id):
        from app.automation.linkedin.details import JobDetails

        return JobDetails(job_id=job_id, description="desc", apply_method="easy_apply")

    monkeypatch.setattr(discovery_mod, "search_jobs", fake_search)
    monkeypatch.setattr(discovery_mod, "fetch_job_details", fake_details)
    monkeypatch.setattr(discovery_mod, "LinkedInClient", lambda *_a, **_k: FakeClient([page]))

    result = await discovery_mod.discover(
        db, session, SearchCriteria(keywords=["dev"]), max_jobs=50
    )

    assert result.fetched == 3
    assert result.new == 2
    assert result.detailed == 2
    assert await repo.exists("new1")
    assert await repo.exists("new2")


async def test_discover_stops_on_session_expired(db: Database, monkeypatch) -> None:
    from app.automation.linkedin.client import SessionExpiredError

    session = LinkedInSession()
    session.set_cookies("tok", "ajax:1")

    async def fake_search(client, criteria, start=0, count=25):
        raise SessionExpiredError("expired")

    monkeypatch.setattr(discovery_mod, "search_jobs", fake_search)
    monkeypatch.setattr(discovery_mod, "LinkedInClient", lambda *_a, **_k: FakeClient([]))

    result = await discovery_mod.discover(
        db, session, SearchCriteria(keywords=["dev"]), max_jobs=50
    )
    assert result.stopped_reason == "session_expired"
    assert result.new == 0
