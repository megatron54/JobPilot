"""Autopilot FastAPI service - entry point.

Runs as a child process of the Tauri host on a local port (default 8765).
Exposes the autopilot control API: session, settings, pipeline, queue.

Run with:
    python -m uvicorn app.automation.main:app --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import logging
import os
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Database, set_db, get_db
from .models import (
    ApiResponse,
    AutopilotConfig,
    PipelineStatus,
    QueueActionUpdate,
    SearchCriteria,
    SessionCookies,
    SessionStatus,
)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
    # Phase 3 will wire this to the real orchestrator state.
    return PipelineStatus(status="idle")


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
