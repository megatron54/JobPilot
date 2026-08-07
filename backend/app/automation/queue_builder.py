"""Build the action queue from scored jobs and execute approved actions.

After scoring, the top jobs get content generated (recruiter note, cover letter)
and queued as pending actions. The user reviews/edits/approves, then approved
actions are executed respecting daily limits.
"""

from __future__ import annotations

import logging

from .content import generate_cover_letter, generate_recruiter_message
from .database import Database
from .executor.connector import _profile_id_from_url, send_connection_request, send_message
from .jobs_repository import JobsRepository
from .limits import can_perform
from .profile import UserProfile
from .queue_manager import QueueManager
from .session import LinkedInSession

logger = logging.getLogger("jobpilot.autopilot.queue_builder")


async def build_queue_for_top_jobs(
    db: Database,
    profile: UserProfile,
    top_n: int = 10,
    min_score: float = 70.0,
) -> int:
    """Generate content and create pending actions for the top scored jobs.

    Returns the number of actions created. Skips jobs that already have actions.
    """
    repo = JobsRepository(db)
    qm = QueueManager(db)
    jobs = await repo.top_scored(limit=top_n, min_score=min_score)
    created = 0

    for job in jobs:
        job_id = job["job_id"]

        # Apply action (one per job)
        if not await _has_action_type(db, job_id, ("apply_easy", "apply_external")):
            apply_type = (
                "apply_easy" if job.get("apply_method") == "easy_apply" else "apply_external"
            )
            description = job.get("description") or ""
            # Emphasize the candidate's own skills that the posting mentions.
            emphasize = [
                s for s in profile.key_skills
                if s and s.lower() in description.lower()
            ]
            cover = await generate_cover_letter(
                profile, job.get("title", ""), job.get("company", ""),
                description, emphasize_keywords=emphasize, refine=True,
            )
            await qm.add(job_id, apply_type, content_draft=cover,
                         priority=int(job.get("score", 0)))
            created += 1

        # Connect action when a recruiter is known, deduped by recruiter URL
        recruiter_url = job.get("recruiter_url") or ""
        if recruiter_url and not await _recruiter_already_queued(db, recruiter_url):
            note = await generate_recruiter_message(
                profile, job.get("title", ""), job.get("company", ""),
                job.get("recruiter_name", ""),
            )
            await qm.add(job_id, "connect", content_draft=note,
                         target_profile_url=recruiter_url,
                         priority=int(job.get("score", 0)))
            created += 1

    logger.info("Queue built: %d actions created", created)
    return created


async def execute_approved_actions(
    db: Database,
    session: LinkedInSession,
    max_connections: int,
    max_messages: int,
    max_applies: int,
) -> dict:
    """Execute all approved write-actions in the queue (connect/message only).

    Applications (browser) are executed via the dedicated /execute/apply endpoint
    so the user can watch; here we handle the API-based connect/message actions.
    """
    qm = QueueManager(db)
    approved = await qm.list_by_status("approved")
    results = {"connected": 0, "messaged": 0, "skipped": 0, "failed": 0}

    for action in approved:
        if action.action_type not in ("connect", "message"):
            continue

        async with db.transaction():
            ok, reason = await can_perform(
                db, action.action_type, max_connections, max_messages, max_applies
            )
            if not ok:
                await qm.update_status(action.id, "skipped")
                results["skipped"] += 1
                logger.info("Skipped action %d: %s", action.id, reason)
                continue

            text = action.content_final or action.content_draft
            profile_id = _profile_id_from_url(action.target_profile_url)

            if action.action_type == "connect":
                # Record the attempt BEFORE the API call so the daily counter can
                # never undercount (a sent-but-unrecorded connection would otherwise
                # let us exceed LinkedIn's limit and risk a ban). Holding the
                # transaction lock across the whole check+record+call+status
                # update prevents another concurrent call from reading a stale
                # daily count in between.
                await _record_connection(db, action.job_id, action.target_profile_url, text)
                outcome = await send_connection_request(session, profile_id, text)
                if outcome.status == "sent":
                    await qm.update_status(action.id, "completed")
                    results["connected"] += 1
                else:
                    await _unrecord_connection(db, action.job_id, action.target_profile_url)
                    await qm.update_status(action.id, "failed")
                    results["failed"] += 1
            else:  # message
                outcome = await send_message(session, profile_id, text)
                if outcome.status == "sent":
                    await qm.update_status(action.id, "completed")
                    results["messaged"] += 1
                else:
                    await qm.update_status(action.id, "failed")
                    results["failed"] += 1

    return results


async def _has_action_type(db: Database, job_id: str, types: tuple[str, ...]) -> bool:
    placeholders = ",".join("?" for _ in types)
    row = await db.fetch_one(
        f"SELECT 1 FROM action_queue WHERE job_id = ? AND action_type IN ({placeholders}) LIMIT 1",
        (job_id, *types),
    )
    return row is not None


async def _recruiter_already_queued(db: Database, recruiter_url: str) -> bool:
    row = await db.fetch_one(
        "SELECT 1 FROM action_queue WHERE action_type='connect' "
        "AND target_profile_url = ? LIMIT 1",
        (recruiter_url,),
    )
    return row is not None


async def _record_connection(db: Database, job_id: str, url: str, note: str) -> None:
    await db.execute(
        "INSERT INTO connections_sent (recruiter_id, job_id, note, status) VALUES (?, ?, ?, 'sent')",
        (url, job_id, note),
    )


async def _unrecord_connection(db: Database, job_id: str, url: str) -> None:
    """Roll back an optimistic connection record when the send actually failed."""
    await db.execute(
        """
        DELETE FROM connections_sent
        WHERE id = (
            SELECT id FROM connections_sent
            WHERE job_id = ? AND recruiter_id = ?
            ORDER BY id DESC LIMIT 1
        )
        """,
        (job_id, url),
    )
