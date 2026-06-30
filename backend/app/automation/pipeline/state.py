"""Shared pipeline state for progress reporting and cancellation."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class PipelineState:
    run_id: str = ""
    status: str = "idle"   # idle/running/completed/failed/cancelled
    stage: str = ""
    progress: int = 0
    total: int = 0
    message: str = ""
    jobs_fetched: int = 0
    jobs_filtered: int = 0
    jobs_scored: int = 0
    jobs_queued: int = 0
    _cancel: bool = field(default=False)

    def start(self) -> str:
        self.run_id = uuid.uuid4().hex
        self.status = "running"
        self.stage = "starting"
        self.progress = 0
        self.total = 0
        self.message = ""
        self.jobs_fetched = 0
        self.jobs_filtered = 0
        self.jobs_scored = 0
        self.jobs_queued = 0
        self._cancel = False
        return self.run_id

    def update(self, stage: str, progress: int, total: int, message: str = "") -> None:
        self.stage = stage
        self.progress = progress
        self.total = total
        if message:
            self.message = message

    def finish(self, status: str = "completed", message: str = "") -> None:
        self.status = status
        self.stage = "done"
        if message:
            self.message = message

    def request_cancel(self) -> None:
        self._cancel = True

    @property
    def cancelled(self) -> bool:
        return self._cancel

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    def snapshot(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "total": self.total,
            "message": self.message,
            "jobs_fetched": self.jobs_fetched,
            "jobs_filtered": self.jobs_filtered,
            "jobs_scored": self.jobs_scored,
            "jobs_queued": self.jobs_queued,
        }


# Module-level singleton + lock to prevent concurrent runs.
state = PipelineState()
run_lock = asyncio.Lock()
