"""Action queue manager - CRUD operations over the action_queue table."""

from __future__ import annotations

import json
import logging

from .database import Database
from .models import QueueAction

logger = logging.getLogger("jobpilot.autopilot.queue")


class QueueManager:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_pending(self) -> list[QueueAction]:
        rows = await self._db.fetch_all(
            """
            SELECT id, job_id, action_type, status, priority,
                   content_draft, content_final, target_profile_url
            FROM action_queue
            WHERE status IN ('pending_review', 'approved', 'edited')
            ORDER BY priority DESC, created_at ASC
            """
        )
        return [self._row_to_action(r) for r in rows]

    async def list_by_status(self, status: str) -> list[QueueAction]:
        rows = await self._db.fetch_all(
            """
            SELECT id, job_id, action_type, status, priority,
                   content_draft, content_final, target_profile_url
            FROM action_queue WHERE status = ?
            ORDER BY priority DESC, created_at ASC
            """,
            (status,),
        )
        return [self._row_to_action(r) for r in rows]

    async def get(self, action_id: int) -> QueueAction | None:
        row = await self._db.fetch_one(
            """
            SELECT id, job_id, action_type, status, priority,
                   content_draft, content_final, target_profile_url
            FROM action_queue WHERE id = ?
            """,
            (action_id,),
        )
        return self._row_to_action(row) if row else None

    async def add(
        self,
        job_id: str,
        action_type: str,
        content_draft: str = "",
        target_profile_url: str = "",
        priority: int = 0,
    ) -> int:
        cur = await self._db.execute(
            """
            INSERT INTO action_queue
                (job_id, action_type, content_draft, target_profile_url, priority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, action_type, content_draft, target_profile_url, priority),
        )
        return cur.lastrowid or 0

    async def update_status(
        self, action_id: int, status: str, content_final: str | None = None
    ) -> bool:
        # Stamp executed_at when an action reaches a terminal executed state so
        # daily-limit counting (which filters on executed_at) works correctly.
        stamp = status in ("completed", "failed", "skipped")
        if content_final is not None:
            await self._db.execute(
                "UPDATE action_queue SET status = ?, content_final = ?"
                + (", executed_at = CURRENT_TIMESTAMP" if stamp else "")
                + " WHERE id = ?",
                (status, content_final, action_id),
            )
        else:
            await self._db.execute(
                "UPDATE action_queue SET status = ?"
                + (", executed_at = CURRENT_TIMESTAMP" if stamp else "")
                + " WHERE id = ?",
                (status, action_id),
            )
        await self._log(action_id, "status_change", json.dumps({"status": status}))
        return True

    async def approve_all_pending(self) -> int:
        cur = await self._db.execute(
            "UPDATE action_queue SET status = 'approved' WHERE status = 'pending_review'"
        )
        return cur.rowcount

    async def reject_all_pending(self) -> int:
        cur = await self._db.execute(
            "UPDATE action_queue SET status = 'rejected' WHERE status = 'pending_review'"
        )
        return cur.rowcount

    async def _log(self, action_id: int, event: str, details: str) -> None:
        await self._db.execute(
            "INSERT INTO execution_log (action_id, event, details) VALUES (?, ?, ?)",
            (action_id, event, details),
        )

    @staticmethod
    def _row_to_action(row) -> QueueAction:
        return QueueAction(
            id=row["id"],
            job_id=row["job_id"],
            action_type=row["action_type"],
            status=row["status"],
            priority=row["priority"],
            content_draft=row["content_draft"] or "",
            content_final=row["content_final"] or "",
            target_profile_url=row["target_profile_url"] or "",
        )
