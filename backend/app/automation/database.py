"""SQLite database layer for the Autopilot service.

Uses aiosqlite with WAL mode for concurrent read/write access. A single
long-lived connection is held for the app lifetime (created in the FastAPI
lifespan). All access goes through the `Database` class.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

logger = logging.getLogger("jobpilot.autopilot.db")

SCHEMA_VERSION = 1
_SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


class Database:
    """Async SQLite wrapper holding a single shared connection."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    async def connect(self) -> None:
        """Open the connection, apply pragmas, and ensure the schema exists."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._path))
        self._conn.row_factory = aiosqlite.Row

        # Pragmas for concurrency and integrity
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.commit()

        await self._init_schema()
        logger.info("Database ready at %s (schema v%d)", self._path, SCHEMA_VERSION)

    async def _init_schema(self) -> None:
        schema_sql = _SCHEMA_FILE.read_text(encoding="utf-8")
        await self.conn.executescript(schema_sql)

        # Record schema version if not present
        cur = await self.conn.execute("SELECT MAX(version) FROM schema_version")
        row = await cur.fetchone()
        current = row[0] if row and row[0] is not None else 0
        if current < SCHEMA_VERSION:
            await self.conn.execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
        await self.conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    # --- Generic helpers -------------------------------------------------

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> aiosqlite.Cursor:
        cur = await self.conn.execute(sql, tuple(params))
        await self.conn.commit()
        return cur

    async def fetch_one(self, sql: str, params: Iterable[Any] = ()) -> aiosqlite.Row | None:
        cur = await self.conn.execute(sql, tuple(params))
        return await cur.fetchone()

    async def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(sql, tuple(params))
        return list(await cur.fetchall())


# Module-level singleton, initialized in the FastAPI lifespan.
_db: Database | None = None


def get_db() -> Database:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


def set_db(db: Database) -> None:
    global _db
    _db = db
