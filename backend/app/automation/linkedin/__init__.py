"""LinkedIn Voyager API client package for the Autopilot service."""

from .client import (
    ChallengeError,
    LinkedInClient,
    LinkedInError,
    RateLimitedError,
    SessionExpiredError,
)
from .details import JobDetails, fetch_job_details
from .people import Recruiter, find_recruiters
from .rate_limiter import RateLimiter
from .search import JobStub, search_jobs

__all__ = [
    "LinkedInClient",
    "LinkedInError",
    "SessionExpiredError",
    "RateLimitedError",
    "ChallengeError",
    "RateLimiter",
    "JobStub",
    "search_jobs",
    "JobDetails",
    "fetch_job_details",
    "Recruiter",
    "find_recruiters",
]
