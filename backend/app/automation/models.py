"""Pydantic models for the Autopilot API (request/response schemas)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- Session ------------------------------------------------------------


class SessionCookies(BaseModel):
    """LinkedIn auth cookies passed from the Tauri host at startup."""

    li_at: str = Field(..., min_length=1)
    jsessionid: str = Field(default="", description="Used for the csrf-token header")


class SessionStatus(BaseModel):
    has_session: bool
    li_at_present: bool
    jsessionid_present: bool
    valid: bool | None = None  # None = not yet checked


# --- Search criteria ----------------------------------------------------


class SearchCriteria(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    location: str = ""
    geo_id: str = ""
    remote: bool = False
    hybrid: bool = False
    onsite: bool = False
    experience_levels: list[str] = Field(default_factory=list)  # 1..6
    job_types: list[str] = Field(default_factory=list)  # F,C,P,T,I
    posted_within_hours: int = 168  # last 7 days
    excluded_companies: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)


# --- Autopilot config ---------------------------------------------------


class AutopilotConfig(BaseModel):
    enabled: bool = False
    schedule_hour: int = 9
    schedule_minute: int = 0
    schedule_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri
    max_connections_per_day: int = 15
    max_messages_per_day: int = 30
    max_applies_per_day: int = 20
    score_threshold: int = 60
    top_n_generate: int = 10


# --- Jobs & queue -------------------------------------------------------


class DiscoveredJob(BaseModel):
    job_id: str
    title: str
    company: str
    location: str = ""
    workplace_type: str = ""
    apply_method: str = ""
    external_url: str = ""
    score: float | None = None
    recommendation: str = ""
    match_reasons: list[str] = Field(default_factory=list)
    deal_breakers: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    recruiter_name: str = ""
    recruiter_url: str = ""
    status: str = "discovered"


class QueueAction(BaseModel):
    id: int
    job_id: str
    action_type: Literal["apply_easy", "apply_external", "connect", "message"]
    status: str
    priority: int = 0
    content_draft: str = ""
    content_final: str = ""
    target_profile_url: str = ""


class QueueActionUpdate(BaseModel):
    status: Literal["approved", "rejected", "edited"] | None = None
    content_final: str | None = None


# --- Pipeline -----------------------------------------------------------


class PipelineStartRequest(BaseModel):
    criteria: SearchCriteria | None = None  # if None, use stored criteria


class PipelineStatus(BaseModel):
    run_id: str | None = None
    status: str = "idle"  # idle/running/completed/failed/cancelled
    stage: str = ""
    progress: int = 0
    total: int = 0
    message: str = ""
    jobs_fetched: int = 0
    jobs_filtered: int = 0
    jobs_scored: int = 0
    jobs_queued: int = 0


# --- Generic ------------------------------------------------------------


class ApiResponse(BaseModel):
    success: bool
    message: str = ""
