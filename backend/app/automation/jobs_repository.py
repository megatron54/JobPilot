"""Repository for discovered jobs (persistence + deduplication)."""

from __future__ import annotations

import json
import logging

from .database import Database
from .linkedin.details import JobDetails
from .linkedin.search import JobStub

logger = logging.getLogger("jobpilot.autopilot.jobs_repo")


class JobsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def exists(self, job_id: str) -> bool:
        row = await self._db.fetch_one(
            "SELECT 1 FROM discovered_jobs WHERE job_id = ?", (job_id,)
        )
        return row is not None

    async def filter_new(self, job_ids: list[str]) -> set[str]:
        """Return the subset of job_ids not already in the database."""
        if not job_ids:
            return set()
        placeholders = ",".join("?" for _ in job_ids)
        rows = await self._db.fetch_all(
            f"SELECT job_id FROM discovered_jobs WHERE job_id IN ({placeholders})",
            job_ids,
        )
        existing = {r["job_id"] for r in rows}
        return {jid for jid in job_ids if jid not in existing}

    async def upsert_stub(self, stub: JobStub) -> None:
        await self._db.execute(
            """
            INSERT INTO discovered_jobs
                (job_id, title, company, company_id, location, workplace_type, status)
            VALUES (?, ?, ?, ?, ?, ?, 'discovered')
            ON CONFLICT(job_id) DO UPDATE SET
                title=excluded.title,
                company=excluded.company,
                company_id=excluded.company_id,
                location=excluded.location,
                workplace_type=excluded.workplace_type
            """,
            (
                stub.job_id,
                stub.title,
                stub.company,
                stub.company_id,
                stub.location,
                stub.workplace_type,
            ),
        )

    async def enrich_details(self, details: JobDetails) -> None:
        await self._db.execute(
            """
            UPDATE discovered_jobs SET
                description = ?,
                apply_method = ?,
                external_url = ?,
                workplace_type = COALESCE(NULLIF(?, ''), workplace_type),
                recruiter_name = ?,
                recruiter_url = ?,
                status = 'detailed'
            WHERE job_id = ?
            """,
            (
                details.description,
                details.apply_method,
                details.external_url,
                details.workplace_type,
                details.recruiter_name,
                details.recruiter_url,
                details.job_id,
            ),
        )

    async def set_score(
        self,
        job_id: str,
        score: float,
        recommendation: str,
        reasons: list[str],
        deal_breakers: list[str],
        missing_skills: list[str],
    ) -> None:
        await self._db.execute(
            """
            UPDATE discovered_jobs SET
                score = ?,
                recommendation = ?,
                score_reasons = ?,
                deal_breakers = ?,
                missing_skills = ?,
                status = 'scored'
            WHERE job_id = ?
            """,
            (
                score,
                recommendation,
                json.dumps(reasons, ensure_ascii=False),
                json.dumps(deal_breakers, ensure_ascii=False),
                json.dumps(missing_skills, ensure_ascii=False),
                job_id,
            ),
        )

    async def count(self) -> int:
        row = await self._db.fetch_one("SELECT COUNT(*) AS c FROM discovered_jobs")
        return int(row["c"]) if row else 0

    async def list_recent(self, limit: int = 50) -> list[dict]:
        rows = await self._db.fetch_all(
            """
            SELECT job_id, title, company, location, workplace_type, apply_method,
                   external_url, score, recommendation, recruiter_name, recruiter_url,
                   status, discovered_at
            FROM discovered_jobs
            ORDER BY discovered_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in rows]

    async def top_scored(self, limit: int = 10, min_score: float = 0.0) -> list[dict]:
        rows = await self._db.fetch_all(
            """
            SELECT job_id, title, company, location, workplace_type, apply_method,
                   external_url, description, score, recommendation, score_reasons,
                   deal_breakers, missing_skills, recruiter_name, recruiter_url
            FROM discovered_jobs
            WHERE score IS NOT NULL AND score >= ?
            ORDER BY score DESC
            LIMIT ?
            """,
            (min_score, limit),
        )
        return [dict(r) for r in rows]
