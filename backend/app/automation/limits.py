"""Daily action limits to stay under LinkedIn's detection thresholds.

Counts actions performed today (from the DB) and reports remaining headroom.
See docs/AUTOPILOT_PLAN.md section 7 for the recommended ceilings.
"""

from __future__ import annotations

from dataclasses import dataclass

from .database import Database


@dataclass
class DailyUsage:
    connections: int
    messages: int
    applies: int


async def usage_today(db: Database) -> DailyUsage:
    connections = await _count_today(
        db, "SELECT COUNT(*) AS c FROM connections_sent WHERE date(sent_at) = date('now')"
    )
    messages = await _count_today(
        db,
        "SELECT COUNT(*) AS c FROM action_queue "
        "WHERE action_type='message' AND status='completed' "
        "AND date(executed_at) = date('now')",
    )
    applies = await _count_today(
        db,
        "SELECT COUNT(*) AS c FROM action_queue "
        "WHERE action_type IN ('apply_easy','apply_external') AND status='completed' "
        "AND date(executed_at) = date('now')",
    )
    return DailyUsage(connections=connections, messages=messages, applies=applies)


async def can_perform(
    db: Database,
    action_type: str,
    max_connections: int,
    max_messages: int,
    max_applies: int,
) -> tuple[bool, str]:
    """Check whether one more action of the given type is within today's limit."""
    usage = await usage_today(db)
    if action_type == "connect":
        if usage.connections >= max_connections:
            return False, f"Daily connection limit reached ({max_connections})"
    elif action_type == "message":
        if usage.messages >= max_messages:
            return False, f"Daily message limit reached ({max_messages})"
    elif action_type in ("apply_easy", "apply_external"):
        if usage.applies >= max_applies:
            return False, f"Daily application limit reached ({max_applies})"
    return True, ""


async def _count_today(db: Database, sql: str) -> int:
    row = await db.fetch_one(sql)
    return int(row["c"]) if row and row["c"] is not None else 0
