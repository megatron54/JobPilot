"""Discovery orchestrator: search LinkedIn, dedupe, persist, enrich.

Read-only half of the daily pipeline. Supports two sources:
  - "guest"  (default): unauthenticated jobs-guest endpoints. Safest, no cookie.
  - "voyager": authenticated Voyager API. Richer data (Easy Apply, recruiter)
               but higher ban risk; needs a valid session.
  - "hybrid": guest for the wide search, Voyager to enrich only the top jobs.

If Voyager fails (session expiry / rate limit / challenge), discovery falls
back to guest automatically. See docs/AUTOPILOT_PLAN.md and the ai-job-search
integration notes.
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
from .linkedin.details import JobDetails, fetch_job_details
from .linkedin.guest import (
    GuestFetchError,
    fetch_guest_detail,
    search_guest,
)
from .linkedin.search import JobStub
from .models import SearchCriteria
from .session import LinkedInSession

logger = logging.getLogger("jobpilot.autopilot.discovery")

_PAGE_SIZE = 25
_GUEST_PAGE_SIZE = 10


@dataclass
class DiscoveryResult:
    fetched: int = 0
    new: int = 0
    detailed: int = 0
    errors: int = 0
    stopped_reason: str = ""
    source_used: str = ""


async def discover(
    db: Database,
    session: LinkedInSession,
    criteria: SearchCriteria,
    max_jobs: int | None = None,
    enrich: bool = True,
    progress=None,
    source: str | None = None,
) -> DiscoveryResult:
    """Run a discovery pass. `progress` is an optional async callback(stage, done, total)."""
    max_jobs = max_jobs or settings.max_jobs_per_run
    source = (source or settings.discovery_source).lower()
    repo = JobsRepository(db)
    result = DiscoveryResult(source_used=source)

    # 1. Search (wide net). Guest is default and needs no session.
    if source == "voyager":
        stubs, reason = await _search_voyager(session, criteria, max_jobs, progress)
        if reason in ("session_expired", "rate_limited", "challenge") and not stubs:
            logger.info("Voyager unavailable (%s); falling back to guest", reason)
            source = "guest"
            result.source_used = "guest (fallback)"
            stubs, reason = await _search_guest(criteria, max_jobs, progress)
    else:  # guest or hybrid both search via guest
        stubs, reason = await _search_guest(criteria, max_jobs, progress)

    result.stopped_reason = reason
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

    # 4. Enrichment. Voyager (richer) for voyager/hybrid when a session exists;
    #    guest otherwise. Note `source` may have been downgraded to guest above.
    if enrich and new_stubs:
        if source in ("voyager", "hybrid") and session.has_session:
            result.detailed, result.errors = await _enrich_voyager(
                session, repo, new_stubs, result.errors, progress
            )
        else:
            result.detailed, result.errors = await _enrich_guest(
                repo, new_stubs, result.errors, progress
            )

    logger.info(
        "Discovery[%s]: fetched=%d new=%d detailed=%d errors=%d reason=%s",
        result.source_used, result.fetched, result.new,
        result.detailed, result.errors, result.stopped_reason or "ok",
    )
    return result


# --- Guest source -------------------------------------------------------


def _guest_remote_mode(criteria: SearchCriteria) -> str:
    if criteria.remote:
        return "remote"
    if criteria.hybrid:
        return "hybrid"
    if criteria.onsite:
        return "onsite"
    return ""


async def _search_guest(criteria, max_jobs, progress) -> tuple[list[JobStub], str]:
    keywords = " ".join(criteria.keywords)
    jobage_days = max(1, (criteria.posted_within_hours or 168) // 24)
    remote = _guest_remote_mode(criteria)
    stubs: list[JobStub] = []
    page = 1
    while len(stubs) < max_jobs:
        try:
            cards = await search_guest(
                keywords, criteria.location, jobage_days, remote, page=page
            )
        except GuestFetchError as exc:
            logger.warning("Guest search failed: %s", exc)
            return stubs, "guest_error" if not stubs else ""
        if not cards:
            break
        for c in cards:
            stubs.append(JobStub(
                job_id=c.id, title=c.title, company=c.company,
                location=c.location, workplace_type=remote,
            ))
        page += 1
        if progress:
            await progress("fetch", len(stubs), max_jobs)
        if len(cards) < _GUEST_PAGE_SIZE:
            break
    return stubs, ""


async def _enrich_guest(repo, stubs, errors, progress) -> tuple[int, int]:
    detailed = 0
    total = len(stubs)
    for i, stub in enumerate(stubs, start=1):
        try:
            gd = await fetch_guest_detail(stub.job_id)
            details = JobDetails(
                job_id=stub.job_id,
                title=gd.title or stub.title,
                company=gd.company or stub.company,
                location=gd.location or stub.location,
                description=gd.description,
                apply_method="external" if gd.apply_url else "",
                external_url=gd.apply_url,
                workplace_type=stub.workplace_type,
            )
            await repo.enrich_details(details)
            detailed += 1
        except GuestFetchError as exc:
            logger.debug("Guest detail failed for %s: %s", stub.job_id, exc)
            errors += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug("Guest enrich error for %s: %s", stub.job_id, exc)
            errors += 1
        if progress:
            await progress("detail", i, total)
        await asyncio.sleep(0)
    return detailed, errors


# --- Voyager source -----------------------------------------------------


async def _search_voyager(session, criteria, max_jobs, progress) -> tuple[list[JobStub], str]:
    stubs: list[JobStub] = []
    start = 0
    async with LinkedInClient(session) as client:
        while len(stubs) < max_jobs:
            try:
                page = await search_jobs(client, criteria, start=start, count=_PAGE_SIZE)
            except SessionExpiredError:
                return stubs, "session_expired"
            except RateLimitedError:
                return stubs, "rate_limited"
            except ChallengeError:
                return stubs, "challenge"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Voyager search failed: %s", exc)
                return stubs, "error"
            if not page:
                break
            stubs.extend(page)
            start += _PAGE_SIZE
            if progress:
                await progress("fetch", len(stubs), max_jobs)
            if len(page) < _PAGE_SIZE:
                break
    return stubs, ""


async def _enrich_voyager(session, repo, stubs, errors, progress) -> tuple[int, int]:
    detailed = 0
    total = len(stubs)
    async with LinkedInClient(session) as client:
        for i, stub in enumerate(stubs, start=1):
            try:
                details = await fetch_job_details(client, stub.job_id)
                await repo.enrich_details(details)
                detailed += 1
            except (SessionExpiredError, RateLimitedError, ChallengeError) as exc:
                logger.info("Stopping Voyager enrichment: %s", exc)
                break
            except Exception as exc:  # noqa: BLE001
                logger.debug("Voyager detail failed for %s: %s", stub.job_id, exc)
                errors += 1
            if progress:
                await progress("detail", i, total)
            await asyncio.sleep(0)
    return detailed, errors
