"""Pipeline orchestrator: discover -> pre-filter -> score -> rank.

Coordinates the full daily run and updates shared progress state. Scoring runs
with bounded concurrency so Ollama (OLLAMA_NUM_PARALLEL) is used efficiently
without overwhelming it. See docs/AUTOPILOT_PLAN.md sections 6 and 8.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from ..config import settings
from ..database import Database
from ..discovery import discover
from ..jobs_repository import JobsRepository
from ..models import SearchCriteria
from ..profile import UserProfile, load_profile
from ..session import LinkedInSession
from .prefilter import prefilter_job
from .scorer import score_job
from .state import PipelineState

logger = logging.getLogger("jobpilot.autopilot.pipeline")


@dataclass
class PipelineResult:
    run_id: str
    fetched: int = 0
    new: int = 0
    filtered_out: int = 0
    scored: int = 0
    qualified: int = 0
    stopped_reason: str = ""


async def run_pipeline(
    db: Database,
    session: LinkedInSession,
    criteria: SearchCriteria,
    state: PipelineState,
    do_discovery: bool = True,
    score_concurrency: int = 4,
) -> PipelineResult:
    """Run the full pipeline. Caller is responsible for the run lock."""
    run_id = state.start()
    repo = JobsRepository(db)
    profile = load_profile()
    result = PipelineResult(run_id=run_id)

    try:
        # Stage 1: discovery (optional - may reuse already-discovered jobs)
        if do_discovery:
            state.update("fetch", 0, 0, "Searching LinkedIn...")

            async def on_progress(stage: str, done: int, total: int) -> None:
                state.update(stage, done, total)

            disc = await discover(
                db, session, criteria, enrich=True, progress=on_progress
            )
            result.fetched = disc.fetched
            result.new = disc.new
            result.stopped_reason = disc.stopped_reason
            state.jobs_fetched = disc.fetched

        if state.cancelled:
            state.finish("cancelled")
            return result

        # Stage 2: load unscored jobs and pre-filter
        jobs = await _load_unscored(db)
        state.update("filter", 0, len(jobs), "Filtering candidates...")
        candidates = []
        for job in jobs:
            decision = prefilter_job(job, profile, criteria)
            if decision.keep:
                candidates.append(job)
            else:
                result.filtered_out += 1
        state.jobs_filtered = len(candidates)

        if state.cancelled:
            state.finish("cancelled")
            return result

        # Stage 3: score candidates with bounded concurrency
        state.update("score", 0, len(candidates), "Scoring with AI...")
        scored = await _score_all(repo, candidates, profile, state, score_concurrency)
        result.scored = scored

        # Stage 4: count qualified (above threshold)
        qualified = await repo.top_scored(
            limit=1000, min_score=float(settings.score_threshold)
        )
        result.qualified = len(qualified)
        state.jobs_queued = len(qualified)

        # Stage 5: build the action queue (content + pending actions) for top jobs
        if not state.cancelled and qualified:
            state.update("generate", 0, 0, "Preparing applications...")
            from ..queue_builder import build_queue_for_top_jobs

            await build_queue_for_top_jobs(
                db, profile,
                top_n=settings.top_n_generate,
                min_score=float(settings.score_threshold),
            )

        state.finish("completed", f"{result.qualified} jobs qualified")
        logger.info(
            "Pipeline %s done: fetched=%d new=%d filtered_out=%d scored=%d qualified=%d",
            run_id, result.fetched, result.new, result.filtered_out,
            result.scored, result.qualified,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed")
        state.finish("failed", str(exc))
        result.stopped_reason = "error"

    return result


async def _load_unscored(db: Database) -> list[dict]:
    rows = await db.fetch_all(
        """
        SELECT job_id, title, company, location, workplace_type, apply_method,
               external_url, description
        FROM discovered_jobs
        WHERE score IS NULL
        ORDER BY discovered_at DESC
        """
    )
    return [dict(r) for r in rows]


async def _score_all(
    repo: JobsRepository,
    candidates: list[dict],
    profile: UserProfile,
    state: PipelineState,
    concurrency: int,
) -> int:
    sem = asyncio.Semaphore(max(1, concurrency))
    done = 0
    scored_count = 0
    total = len(candidates)
    lock = asyncio.Lock()

    async def worker(job: dict) -> None:
        nonlocal done, scored_count
        if state.cancelled:
            return
        async with sem:
            result = await score_job(job, profile)
        await repo.set_score(
            result.job_id,
            result.score,
            result.recommendation,
            result.match_reasons,
            result.deal_breakers,
            result.missing_skills,
        )
        async with lock:
            done += 1
            scored_count += 1
            state.update("score", done, total)

    await asyncio.gather(*(worker(j) for j in candidates), return_exceptions=True)
    return scored_count
