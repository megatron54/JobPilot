"""Map the user profile to common application form fields, and detect the ATS.

The mapping and ATS detection are pure functions (unit-testable). The browser
flows that use them live in browser.py / easy_apply.py / form_filler/.
See docs/AUTOPILOT_PLAN.md section 11.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..profile import UserProfile

# Field categories the system understands.
FIELD_CATEGORIES = {
    "first_name",
    "last_name",
    "full_name",
    "email",
    "phone",
    "linkedin_url",
    "location",
    "city",
    "current_title",
    "current_company",
    "experience_years",
    "resume_upload",
    "cover_letter",
    "website",
    "salary_expectation",
    "work_authorization",
    "start_date",
    "custom_question",
    "consent_checkbox",
    "unknown",
}

# ATS host patterns -> adapter name.
ATS_PATTERNS: dict[str, tuple[str, ...]] = {
    "greenhouse": ("boards.greenhouse.io", "job-boards.greenhouse.io", "greenhouse.io"),
    "lever": ("jobs.lever.co", "lever.co"),
    "workday": ("myworkdayjobs.com", "myworkday.com", "wd1.myworkdayjobs.com",
                "wd5.myworkday.com"),
    "smartrecruiters": ("jobs.smartrecruiters.com", "smartrecruiters.com"),
    "bamboohr": ("bamboohr.com",),
    "ashby": ("jobs.ashbyhq.com", "ashbyhq.com"),
    "workable": ("apply.workable.com", "workable.com"),
}


def detect_ats(url: str) -> str:
    """Return the ATS name for a job application URL, or 'generic'."""
    if not url:
        return "generic"
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "generic"
    for ats, patterns in ATS_PATTERNS.items():
        if any(host == p or host.endswith("." + p) or host.endswith(p) for p in patterns):
            return ats
    return "generic"


def value_for_field(category: str, profile: UserProfile, extra: dict | None = None) -> str:
    """Return the value to fill for a known field category from the profile.

    `extra` may carry computed values (cover_letter, salary, work_auth, etc.).
    Returns "" when there is no confident value (caller decides what to do).
    """
    extra = extra or {}
    first, last = _split_name(profile.name)

    mapping = {
        "first_name": first,
        "last_name": last,
        "full_name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "linkedin_url": profile.linkedin_url,
        "location": profile.location,
        "city": _city_of(profile.location),
        "current_title": profile.title,
        "experience_years": _years_str(profile.years_experience),
        "website": profile.linkedin_url,
    }
    if category in mapping:
        return mapping[category]
    # Computed/configurable values supplied by the caller.
    if category in ("cover_letter", "salary_expectation", "work_authorization",
                    "start_date", "current_company"):
        return str(extra.get(category, ""))
    return ""


def _split_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _city_of(location: str) -> str:
    if not location:
        return ""
    return location.split(",")[0].strip()


def _years_str(years: float) -> str:
    if years <= 0:
        return ""
    if years == int(years):
        return str(int(years))
    return f"{years:.1f}"
