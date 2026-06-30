"""Application executor: route a job to the right apply flow."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..profile import UserProfile
from ..session import LinkedInSession
from .browser import BrowserUnavailableError, browser_page
from .easy_apply import easy_apply
from .field_mapping import detect_ats
from .form_filler.filler import fill_external_form

logger = logging.getLogger("jobpilot.autopilot.applicator")


@dataclass
class ExecutionResult:
    job_id: str
    kind: str              # easy_apply / external
    status: str
    detail: str = ""
    ats: str = ""


async def execute_application(
    session: LinkedInSession,
    profile: UserProfile,
    job_id: str,
    apply_method: str,
    external_url: str = "",
    cv_path: str | None = None,
    cv_text: str = "",
    job_title: str = "",
    company: str = "",
    extra_values: dict | None = None,
    auto_submit: bool = False,
) -> ExecutionResult:
    """Open a visible browser and run the appropriate apply flow.

    Never auto-submits unless auto_submit=True (default False -> user confirms).
    """
    try:
        if apply_method == "easy_apply":
            async with browser_page(session=session, headless=False) as page:
                outcome = await easy_apply(
                    page, job_id, profile, cv_path, cv_text,
                    job_title, company, auto_submit=auto_submit,
                )
                # Keep the browser long enough for the user to review/submit.
                if outcome.status == "needs_review":
                    await page.wait_for_timeout(60000)
                return ExecutionResult(
                    job_id, "easy_apply", outcome.status, outcome.detail, "linkedin"
                )

        # External application
        if not external_url:
            return ExecutionResult(job_id, "external", "failed", "No external URL")
        ats = detect_ats(external_url)
        async with browser_page(session=session, headless=False, inject_linkedin=False) as page:
            outcome = await fill_external_form(
                page, external_url, profile, cv_path, cv_text,
                job_title, company, extra_values,
            )
            if outcome.status.startswith("filled") or outcome.status in (
                "captcha", "account_required"
            ):
                await page.wait_for_timeout(60000)
            return ExecutionResult(job_id, "external", outcome.status, outcome.detail, ats)

    except BrowserUnavailableError as exc:
        return ExecutionResult(job_id, "unknown", "browser_unavailable", str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Application execution failed for %s", job_id)
        return ExecutionResult(job_id, "unknown", "failed", str(exc))
