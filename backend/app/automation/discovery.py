"""Discovery orchestrator: search LinkedIn, dedupe, persist, enrich.

This is the read-only half of the daily pipeline. It fetches job listings via
the Voyager API, removes already-seen jobs, persists the new ones, and (best
effort) enriches them with full details. Scoring/generation happen in Phase 3.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from .config import settings
from .database import Database
from .jobs_repository import JobsRepository
from .linkedin import LinkedInClient, search_jobs
from .linkedin.client import ChallengeError, RateLimitedError, SessionExpiredError
from .linkedin.details import fetch_job_details
from .models import SearchCriteria
from .session import LinkedInSession

logger = logging.getLogger("jobpilot.autopilot.discovery")


@dataclass
class DiscoveryResult:
    fetched: int = 0
    new: int = 0
    detailed: int = 0
    errors: int = 0
    stopped_reason: str = ""


async def discover(
    db: Database,
    session: LinkedInSession,
    criteria: SearchCriteria,
    max_jobs: int | None = None,
    enrich: bool = True,
    progress=None,
) -> DiscoveryResult:
    """Run a discovery pass. `progress` is an optional async callback(stage, done, total)."""
    max_jobs = max_jobs or settings.max_jobs_per_run
    repo = JobsRepository(db)
    result = DiscoveryResult()

    async with LinkedInClient(session) as client:
        # 1. Page through search results until we have enough or run out.
        stubs = []
        start = 0
        page_size = 25
        while len(stubs) < max_jobs:
            try:
                page = await search_jobs(client, criteria, start=start, count=page_size)
            except SessionExpiredError:
                result.stopped_reason = "session_expired"
                break
            except RateLimitedError:
                result.stopped_reason = "rate_limited"
                break
            except ChallengeError:
                result.stopped_reason = "challenge"
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Search page failed: %s", exc)
                result.errors += 1
                break

            if not page:
                break
            stubs.extend(page)
            start += page_size
            if progress:
                await progress("fetch", len(stubs), max_jobs)
            if len(page) < page_size:
                break  # last page

        stubs = stubs[:max_jobs]
        result.fetched = len(stubs)

        # 2. Deduplicate against the database.
        ids = [s.job_id for s in stubs]
        new_ids = await repo.filter_new(ids)
        new_stubs = [s for s in stubs if s.job_id in new_ids]
        result.new = len(new_stubs)

        # 3. Persist the new stubs.
        for stub in new_stubs:
            await repo.upsert_stub(stub)

        # 4. Best-effort detail enrichment for new jobs.
        if enrich and new_stubs and not result.stopped_reason:
            result.detailed, result.errors = await _enrich_all(
                client, repo, new_stubs, result.errors, progress
            )

    logger.info(
        "Discovery: fetched=%d new=%d detailed=%d errors=%d reason=%s",
        result.fetched,
        result.new,
        result.detailed,
        result.errors,
        result.stopped_reason or "ok",
    )
    return result


async def _enrich_all(client, repo, stubs, errors, progress) -> tuple[int, int]:
    detailed = 0
    total = len(stubs)
    for i, stub in enumerate(stubs, start=1):
        try:
            details = await fetch_job_details(client, stub.job_id)
            await repo.enrich_details(details)
            detailed += 1
        except (SessionExpiredError, RateLimitedError, ChallengeError) as exc:
            logger.info("Stopping enrichment: %s", exc)
            break
        except Exception as exc:  # noqa: BLE001
            logger.debug("Detail fetch failed for %s: %s", stub.job_id, exc)
            errors += 1
        if progress:
            await progress("detail", i, total)
        await asyncio.sleep(0)  # cooperative yield
    return detailed, errors
