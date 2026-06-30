"""Tests for the jobs repository (dedup + persistence)."""

from __future__ import annotations

import pytest

from app.automation.database import Database
from app.automation.jobs_repository import JobsRepository
from app.automation.linkedin.details import JobDetails
from app.automation.linkedin.search import JobStub

pytestmark = pytest.mark.asyncio


async def test_upsert_and_exists(db: Database) -> None:
    repo = JobsRepository(db)
    assert await repo.exists("j1") is False
    await repo.upsert_stub(JobStub(job_id="j1", title="Dev", company="Acme"))
    assert await repo.exists("j1") is True


async def test_filter_new(db: Database) -> None:
    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="j1", title="A", company="X"))
    new = await repo.filter_new(["j1", "j2", "j3"])
    assert new == {"j2", "j3"}


async def test_filter_new_empty(db: Database) -> None:
    repo = JobsRepository(db)
    assert await repo.filter_new([]) == set()


async def test_upsert_is_idempotent(db: Database) -> None:
    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="j1", title="A", company="X"))
    await repo.upsert_stub(JobStub(job_id="j1", title="A updated", company="X"))
    assert await repo.count() == 1
    jobs = await repo.list_recent()
    assert jobs[0]["title"] == "A updated"


async def test_enrich_details(db: Database) -> None:
    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="j1", title="A", company="X"))
    await repo.enrich_details(
        JobDetails(
            job_id="j1",
            description="Full desc",
            apply_method="easy_apply",
            recruiter_name="Jane",
            recruiter_url="https://linkedin.com/in/jane/",
        )
    )
    jobs = await repo.list_recent()
    assert jobs[0]["apply_method"] == "easy_apply"
    assert jobs[0]["recruiter_name"] == "Jane"
    assert jobs[0]["status"] == "detailed"


async def test_set_score_and_top_scored(db: Database) -> None:
    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="low", title="A", company="X"))
    await repo.upsert_stub(JobStub(job_id="high", title="B", company="Y"))
    await repo.set_score("low", 45.0, "partial", ["ok"], [], ["GraphQL"])
    await repo.set_score("high", 90.0, "strong_match", ["great"], [], [])

    top = await repo.top_scored(limit=10, min_score=60.0)
    assert len(top) == 1
    assert top[0]["job_id"] == "high"
    assert top[0]["score"] == 90.0
