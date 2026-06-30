"""Tests for the database layer and schema."""

from __future__ import annotations

import pytest

from app.automation.database import SCHEMA_VERSION, Database

pytestmark = pytest.mark.asyncio


async def test_schema_version_recorded(db: Database) -> None:
    row = await db.fetch_one("SELECT MAX(version) AS v FROM schema_version")
    assert row is not None
    assert row["v"] == SCHEMA_VERSION


async def test_core_tables_exist(db: Database) -> None:
    expected = {
        "discovered_jobs",
        "action_queue",
        "companies",
        "recruiters",
        "connections_sent",
        "pipeline_runs",
        "pipeline_items",
        "llm_cache",
        "execution_log",
    }
    rows = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r["name"] for r in rows}
    assert expected.issubset(names)


async def test_wal_mode_enabled(db: Database) -> None:
    row = await db.fetch_one("PRAGMA journal_mode")
    assert row is not None
    assert row[0].lower() == "wal"


async def test_insert_and_read_discovered_job(db: Database) -> None:
    await db.execute(
        "INSERT INTO discovered_jobs (job_id, title, company) VALUES (?, ?, ?)",
        ("123", "React Dev", "Acme"),
    )
    row = await db.fetch_one(
        "SELECT title, company, status FROM discovered_jobs WHERE job_id = ?", ("123",)
    )
    assert row is not None
    assert row["title"] == "React Dev"
    assert row["company"] == "Acme"
    assert row["status"] == "discovered"


async def test_connect_is_idempotent(db: Database) -> None:
    # Re-running schema init should not error or duplicate versions.
    await db._init_schema()
    rows = await db.fetch_all("SELECT version FROM schema_version")
    assert len(rows) == 1
