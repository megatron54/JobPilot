"""Tests for the action queue manager."""

from __future__ import annotations

import pytest

from app.automation.database import Database
from app.automation.queue_manager import QueueManager

pytestmark = pytest.mark.asyncio


async def _seed_job(db: Database, job_id: str = "j1") -> None:
    await db.execute(
        "INSERT INTO discovered_jobs (job_id, title, company) VALUES (?, ?, ?)",
        (job_id, "Dev", "Acme"),
    )


async def test_add_and_get(db: Database) -> None:
    await _seed_job(db)
    qm = QueueManager(db)
    action_id = await qm.add("j1", "connect", content_draft="Hi there")
    assert action_id > 0

    action = await qm.get(action_id)
    assert action is not None
    assert action.action_type == "connect"
    assert action.content_draft == "Hi there"
    assert action.status == "pending_review"


async def test_list_pending(db: Database) -> None:
    await _seed_job(db)
    qm = QueueManager(db)
    await qm.add("j1", "connect", priority=1)
    await qm.add("j1", "message", priority=5)
    pending = await qm.list_pending()
    assert len(pending) == 2
    # Higher priority comes first
    assert pending[0].priority == 5


async def test_update_status_and_final_content(db: Database) -> None:
    await _seed_job(db)
    qm = QueueManager(db)
    action_id = await qm.add("j1", "message", content_draft="draft")
    await qm.update_status(action_id, "approved", content_final="final text")
    action = await qm.get(action_id)
    assert action is not None
    assert action.status == "approved"
    assert action.content_final == "final text"


async def test_approve_all_pending(db: Database) -> None:
    await _seed_job(db)
    qm = QueueManager(db)
    await qm.add("j1", "connect")
    await qm.add("j1", "message")
    count = await qm.approve_all_pending()
    assert count == 2
    approved = await qm.list_by_status("approved")
    assert len(approved) == 2


async def test_reject_all_pending(db: Database) -> None:
    await _seed_job(db)
    qm = QueueManager(db)
    await qm.add("j1", "connect")
    count = await qm.reject_all_pending()
    assert count == 1
    rejected = await qm.list_by_status("rejected")
    assert len(rejected) == 1
