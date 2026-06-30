"""Tests for the connector helpers, daily limits, and queue builder."""

from __future__ import annotations

import pytest

from app.automation.database import Database
from app.automation.executor.connector import _profile_id_from_url
from app.automation.jobs_repository import JobsRepository
from app.automation.limits import can_perform, usage_today
from app.automation.linkedin.search import JobStub
from app.automation.profile import UserProfile
from app.automation.queue_manager import QueueManager

pytestmark = pytest.mark.asyncio


# --- connector URL parsing ---------------------------------------------


def test_profile_id_from_url() -> None:
    assert _profile_id_from_url("https://www.linkedin.com/in/ada-lovelace/") == "ada-lovelace"
    assert _profile_id_from_url("https://linkedin.com/in/john") == "john"
    assert _profile_id_from_url("") == ""


# --- daily limits -------------------------------------------------------


async def test_usage_today_empty(db: Database) -> None:
    usage = await usage_today(db)
    assert usage.connections == 0
    assert usage.messages == 0
    assert usage.applies == 0


async def test_can_perform_within_limit(db: Database) -> None:
    ok, reason = await can_perform(db, "connect", 15, 30, 20)
    assert ok is True
    assert reason == ""


async def test_can_perform_connection_limit(db: Database) -> None:
    # Seed 2 connections today
    await db.execute("INSERT INTO connections_sent (recruiter_id, status) VALUES ('a', 'sent')")
    await db.execute("INSERT INTO connections_sent (recruiter_id, status) VALUES ('b', 'sent')")
    ok, reason = await can_perform(db, "connect", 2, 30, 20)
    assert ok is False
    assert "limit" in reason.lower()


# --- queue builder ------------------------------------------------------


async def test_build_queue_creates_actions(db: Database, monkeypatch) -> None:
    from app.automation import queue_builder

    repo = JobsRepository(db)
    await repo.upsert_stub(JobStub(job_id="j1", title="React Dev", company="Acme"))
    await repo.set_score("j1", 90.0, "strong_match", ["good"], [], [])
    # Add a recruiter to trigger a connect action
    await db.execute(
        "UPDATE discovered_jobs SET recruiter_url = ?, recruiter_name = ?, apply_method = ? WHERE job_id = ?",
        ("https://linkedin.com/in/jane/", "Jane", "easy_apply", "j1"),
    )

    async def fake_cover(*a, **k):
        return "Cover letter text"

    async def fake_msg(*a, **k):
        return "Hi Jane, interested in the role"

    monkeypatch.setattr(queue_builder, "generate_cover_letter", fake_cover)
    monkeypatch.setattr(queue_builder, "generate_recruiter_message", fake_msg)

    created = await queue_builder.build_queue_for_top_jobs(
        db, UserProfile(name="Ada"), top_n=10, min_score=70.0
    )
    assert created == 2  # apply + connect

    qm = QueueManager(db)
    pending = await qm.list_pending()
    types = {a.action_type for a in pending}
    assert "apply_easy" in types
    assert "connect" in types


async def test_build_queue_skips_existing(db: Database, monkeypatch) -> None:
    from app.automation import queue_builder

    repo = JobsRepository(db)
    qm = QueueManager(db)
    await repo.upsert_stub(JobStub(job_id="j1", title="Dev", company="X"))
    await repo.set_score("j1", 85.0, "good", [], [], [])
    await qm.add("j1", "apply_easy")  # already has an action

    async def fake_cover(*a, **k):
        return "x"

    monkeypatch.setattr(queue_builder, "generate_cover_letter", fake_cover)

    created = await queue_builder.build_queue_for_top_jobs(db, UserProfile(), min_score=70.0)
    assert created == 0
