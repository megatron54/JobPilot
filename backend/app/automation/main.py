"""Autopilot FastAPI service - entry point.

Runs as a child process of the Tauri host on a local port (default 8765).
Exposes the autopilot control API: session, settings, pipeline, queue.

Run with:
    python -m uvicorn app.automation.main:app --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .database import Database, set_db, get_db
from .discovery import discover
from .jobs_repository import JobsRepository
from .models import (
    ApiResponse,
    AutopilotConfig,
    PipelineStatus,
    QueueActionUpdate,
    SearchCriteria,
    SessionCookies,
    SessionStatus,
)
from .pipeline import run_pipeline, state as pipeline_state, run_lock
from .queue_manager import QueueManager
from .session import session
from . import store

logger = logging.getLogger("jobpilot.autopilot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    db = Database(settings.db_path)
    await db.connect()
    set_db(db)
    logger.info("Autopilot service started on %s:%d", settings.host, settings.port)
    logger.info("  Data dir: %s", settings.data_dir)
    logger.info("  DB: %s", settings.db_path)
    yield
    await db.close()
    logger.info("Autopilot service stopped")


app = FastAPI(
    title="JobPilot Autopilot",
    description="Daily job discovery, matching and application automation",
    version="0.1.0",
    lifespan=lifespan,
)

# The service is reached server-side from the Tauri (Rust) host, not directly
# from a browser. CORS is therefore restricted to local origins and does not
# combine credentials with a wildcard (which is invalid and unsafe).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|tauri://localhost)$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


# --- Health & lifecycle -------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "autopilot",
        "version": "0.1.0",
        "has_session": session.has_session,
    }


@app.post("/shutdown", response_model=ApiResponse)
async def shutdown() -> ApiResponse:
    """Graceful shutdown requested by the Tauri host."""
    logger.info("Shutdown requested")

    def _stop() -> None:
        os.kill(os.getpid(), signal.SIGTERM)

    # Schedule termination after the response is sent.
    import threading

    threading.Timer(0.5, _stop).start()
    return ApiResponse(success=True, message="Shutting down")


# --- Session ------------------------------------------------------------


@app.post("/autopilot/session", response_model=SessionStatus)
async def set_session(cookies: SessionCookies) -> SessionStatus:
    session.set_cookies(cookies.li_at, cookies.jsessionid)
    return SessionStatus(
        has_session=session.has_session,
        li_at_present=bool(session.li_at),
        jsessionid_present=bool(session.jsessionid),
        valid=session.valid,
    )


@app.get("/autopilot/session", response_model=SessionStatus)
async def get_session() -> SessionStatus:
    return SessionStatus(
        has_session=session.has_session,
        li_at_present=bool(session.li_at),
        jsessionid_present=bool(session.jsessionid),
        valid=session.valid,
    )


# --- Settings -----------------------------------------------------------


@app.get("/autopilot/settings/criteria", response_model=SearchCriteria)
async def get_criteria() -> SearchCriteria:
    return store.load_search_criteria()


@app.put("/autopilot/settings/criteria", response_model=ApiResponse)
async def put_criteria(criteria: SearchCriteria) -> ApiResponse:
    store.save_search_criteria(criteria)
    return ApiResponse(success=True, message="Criteria saved")


@app.get("/autopilot/settings/config", response_model=AutopilotConfig)
async def get_config() -> AutopilotConfig:
    return store.load_config()


@app.put("/autopilot/settings/config", response_model=ApiResponse)
async def put_config(config: AutopilotConfig) -> ApiResponse:
    store.save_config(config)
    return ApiResponse(success=True, message="Config saved")


# --- Pipeline (stubs in Phase 1; implemented in Phase 3) ----------------


@app.get("/autopilot/status", response_model=PipelineStatus)
async def pipeline_status() -> PipelineStatus:
    return PipelineStatus(**pipeline_state.snapshot())


@app.post("/autopilot/pipeline/run")
async def pipeline_run() -> dict:
    """Run the full pipeline (discover -> filter -> score) in the background."""
    if not session.has_session:
        raise HTTPException(status_code=400, detail="No LinkedIn session. Log in first.")
    criteria = store.load_search_criteria()
    if not criteria.keywords:
        raise HTTPException(status_code=400, detail="No search keywords configured.")
    if pipeline_state.is_running:
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress.")

    async def _run() -> None:
        async with run_lock:
            await run_pipeline(get_db(), session, criteria, pipeline_state)

    asyncio.create_task(_run())
    return {"started": True, "status": pipeline_state.snapshot()}


@app.post("/autopilot/pipeline/cancel", response_model=ApiResponse)
async def pipeline_cancel() -> ApiResponse:
    pipeline_state.request_cancel()
    return ApiResponse(success=True, message="Cancellation requested")


@app.get("/autopilot/pipeline/events")
async def pipeline_events() -> EventSourceResponse:
    """Server-Sent Events stream of pipeline progress."""

    async def event_generator():
        last = None
        # Stream until the run completes, then send a final event.
        while True:
            snap = pipeline_state.snapshot()
            if snap != last:
                yield {"event": "progress", "data": json.dumps(snap)}
                last = snap
            if snap["status"] in ("completed", "failed", "cancelled", "idle"):
                break
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


# --- Discovery ----------------------------------------------------------


@app.post("/autopilot/discover")
async def run_discovery() -> dict:
    """Run a discovery pass using the stored search criteria.

    Requires an active LinkedIn session (cookies forwarded by the Tauri host).
    """
    if not session.has_session:
        raise HTTPException(status_code=400, detail="No LinkedIn session. Log in first.")

    criteria = store.load_search_criteria()
    if not criteria.keywords:
        raise HTTPException(status_code=400, detail="No search keywords configured.")

    result = await discover(get_db(), session, criteria)
    return {
        "fetched": result.fetched,
        "new": result.new,
        "detailed": result.detailed,
        "errors": result.errors,
        "stopped_reason": result.stopped_reason,
    }


@app.get("/autopilot/jobs")
async def list_jobs(limit: int = 50, scored_only: bool = False, min_score: float = 0.0) -> dict:
    repo = JobsRepository(get_db())
    if scored_only:
        jobs = await repo.top_scored(limit=limit, min_score=min_score)
    else:
        jobs = await repo.list_recent(limit=limit)
    total = await repo.count()
    return {"jobs": jobs, "total": total}


# --- Execution (Phase 5: applications) ----------------------------------


@app.post("/autopilot/execute/apply")
async def execute_apply(payload: dict) -> dict:
    """Execute an application for a discovered job in a visible browser.

    By default does NOT auto-submit: the browser is left open for the user to
    review and confirm. Requires an active LinkedIn session for Easy Apply.
    """
    job_id = str(payload.get("job_id", ""))
    auto_submit = bool(payload.get("auto_submit", False))
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id is required")

    row = await get_db().fetch_one(
        """
        SELECT job_id, title, company, apply_method, external_url
        FROM discovered_jobs WHERE job_id = ?
        """,
        (job_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if row["apply_method"] == "easy_apply" and not session.has_session:
        raise HTTPException(status_code=400, detail="No LinkedIn session for Easy Apply")

    from .cv_locator import find_cv_path, read_cv_text
    from .executor import execute_application
    from .profile import load_profile

    result = await execute_application(
        session=session,
        profile=load_profile(),
        job_id=job_id,
        apply_method=row["apply_method"] or "external",
        external_url=row["external_url"] or "",
        cv_path=find_cv_path(),
        cv_text=read_cv_text(),
        job_title=row["title"] or "",
        company=row["company"] or "",
        auto_submit=auto_submit,
    )
    return {
        "job_id": result.job_id,
        "kind": result.kind,
        "status": result.status,
        "detail": result.detail,
        "ats": result.ats,
    }


# --- Queue --------------------------------------------------------------


@app.get("/autopilot/queue")
async def list_queue() -> dict:
    qm = QueueManager(get_db())
    actions = await qm.list_pending()
    return {"actions": [a.model_dump() for a in actions]}


@app.patch("/autopilot/queue/{action_id}", response_model=ApiResponse)
async def update_queue_action(action_id: int, update: QueueActionUpdate) -> ApiResponse:
    qm = QueueManager(get_db())
    action = await qm.get(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    if update.status is not None:
        new_status = "approved" if update.status == "edited" else update.status
        await qm.update_status(action_id, new_status, update.content_final)
    elif update.content_final is not None:
        await qm.update_status(action_id, action.status, update.content_final)

    return ApiResponse(success=True, message="Action updated")


@app.post("/autopilot/queue/approve-all", response_model=ApiResponse)
async def approve_all() -> ApiResponse:
    qm = QueueManager(get_db())
    count = await qm.approve_all_pending()
    return ApiResponse(success=True, message=f"Approved {count} actions")


@app.post("/autopilot/queue/reject-all", response_model=ApiResponse)
async def reject_all() -> ApiResponse:
    qm = QueueManager(get_db())
    count = await qm.reject_all_pending()
    return ApiResponse(success=True, message=f"Rejected {count} actions")
