"""Tests for the security fixes in the execution layer (Phases 5-6)."""

from __future__ import annotations

import pytest

from app.automation.database import Database
from app.automation.executor.connector import _profile_id_from_url, _sanitize_note
from app.automation.limits import can_perform, usage_today
from app.automation.queue_manager import QueueManager

pytestmark = pytest.mark.asyncio


async def _seed_job(db: Database, job_id: str = "j1") -> None:
    await db.execute(
        "INSERT INTO discovered_jobs (job_id, title, company) VALUES (?, ?, ?)",
        (job_id, "Dev", "Acme"),
    )


# --- C1: executed_at stamped so applies/messages count against limits -----


async def test_completed_action_sets_executed_at(db: Database) -> None:
    await _seed_job(db)
    qm = QueueManager(db)
    action_id = await qm.add("j1", "apply_easy")
    await qm.update_status(action_id, "completed")

    row = await db.fetch_one(
        "SELECT executed_at FROM action_queue WHERE id = ?", (action_id,)
    )
    assert row["executed_at"] is not None


async def test_apply_limit_counts_completed_today(db: Database) -> None:
    await _seed_job(db)
    qm = QueueManager(db)
    # Two completed applies today
    for _ in range(2):
        aid = await qm.add("j1", "apply_easy")
        await qm.update_status(aid, "completed")

    usage = await usage_today(db)
    assert usage.applies == 2

    ok, reason = await can_perform(db, "apply_easy", 15, 30, 2)
    assert ok is False
    assert "limit" in reason.lower()


async def test_message_limit_counts_completed(db: Database) -> None:
    await _seed_job(db)
    qm = QueueManager(db)
    aid = await qm.add("j1", "message")
    await qm.update_status(aid, "completed")
    usage = await usage_today(db)
    assert usage.messages == 1


# --- H2: robust profile id parsing --------------------------------------


def test_profile_id_strips_query_params() -> None:
    url = "https://www.linkedin.com/in/ada-lovelace/?lipi=abc123&trk=xyz"
    assert _profile_id_from_url(url) == "ada-lovelace"


def test_profile_id_rejects_garbage() -> None:
    # A path without /in/ should not return a random segment.
    assert _profile_id_from_url("https://linkedin.com/company/acme/") == ""


def test_profile_id_accepts_bare_urn() -> None:
    assert _profile_id_from_url("ACoAABxxxxx") == "ACoAABxxxxx"


# --- M5: connection note sanitization -----------------------------------


def test_sanitize_note_strips_urls_and_emails() -> None:
    note = "Hi! Check https://example.com or email me at me@example.com please"
    cleaned = _sanitize_note(note)
    assert "http" not in cleaned
    assert "@" not in cleaned
    assert "Hi!" in cleaned


def test_sanitize_note_collapses_whitespace() -> None:
    assert _sanitize_note("a    b\n\nc") == "a b c"
