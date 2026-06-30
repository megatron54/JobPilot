"""Shared pytest fixtures for autopilot tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from app.automation.database import Database


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> Database:
    """A fresh in-temp-dir database per test."""
    database = Database(tmp_path / "test_autopilot.db")
    await database.connect()
    yield database
    await database.close()
