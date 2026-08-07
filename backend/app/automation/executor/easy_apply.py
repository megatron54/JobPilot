"""LinkedIn Easy Apply automation (visible browser, supervised).

Drives the multi-step Easy Apply modal: contact info, resume, screening
questions. Pauses before the final Submit so the user confirms. This is
inherently fragile against LinkedIn UI changes; selectors are centralized and
failures degrade to a manual hand-off.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..profile import UserProfile
from .answers import answer_text_question, choose_option

# Labels matching any of these keywords are never auto-answered by the LLM.
# These are legally/factually sensitive questions (work authorization, visa
# sponsorship, EEO self-identification, security clearance, etc.) where a
# hallucinated or wrong answer submitted on a real application could have
# real consequences for the candidate. They are left blank for the user to
# fill in manually before submitting.
_SENSITIVE_LABEL_KEYWORDS = (
    "authoriz",  # work authorization / authorized to work
    "sponsor",  # visa sponsorship
    "visa",
    "citizen",
    "legally",
    "security clearance",
    "clearance",
    "disability",
    "veteran",
    "race",
    "ethnic",
    "gender",
    "pronoun",
    "background check",
    "criminal",
    "felony",
    "salary",  # salary expectations should be set deliberately, not guessed
    "compensation",
)


def is_sensitive_label(label: str) -> bool:
    low = (label or "").lower()
    return any(k in low for k in _SENSITIVE_LABEL_KEYWORDS)

logger = logging.getLogger("jobpilot.autopilot.easy_apply")

_JOB_URL = "https://www.linkedin.com/jobs/view/{job_id}/"
_MAX_STEPS = 8


@dataclass
class ApplyOutcome:
    job_id: str
    status: str            # submitted / needs_review / failed / not_easy_apply
    detail: str = ""
    steps_completed: int = 0


async def easy_apply(
    page,
    job_id: str,
    profile: UserProfile,
    cv_path: str | None = None,
    cv_text: str = "",
    job_title: str = "",
    company: str = "",
    auto_submit: bool = False,
) -> ApplyOutcome:
    """Run the Easy Apply flow. With auto_submit=False, stops before the final
    Submit and returns 'needs_review' for the user to confirm in the open browser.
    """
    try:
        await page.goto(_JOB_URL.format(job_id=job_id), wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        if not await _open_easy_apply(page):
            return ApplyOutcome(job_id, "not_easy_apply", "No Easy Apply button found")

        steps = 0
        while steps < _MAX_STEPS:
            steps += 1
            await _fill_visible_fields(page, profile, cv_path, cv_text, job_title, company)

            if await _has_submit(page):
                if auto_submit:
                    await _click_submit(page)
                    return ApplyOutcome(job_id, "submitted", "Submitted", steps)
                return ApplyOutcome(
                    job_id, "needs_review",
                    "Ready to submit - confirm in the browser", steps,
                )

            if not await _click_next(page):
                return ApplyOutcome(
                    job_id, "needs_review",
                    "Could not advance automatically - continue manually", steps,
                )
            await page.wait_for_timeout(1200)

        return ApplyOutcome(job_id, "needs_review", "Too many steps - finish manually", steps)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Easy Apply failed for %s", job_id)
        return ApplyOutcome(job_id, "failed", str(exc))


async def _open_easy_apply(page) -> bool:
    selectors = [
        "button.jobs-apply-button",
        "button[aria-label*='Easy Apply']",
        "button:has-text('Easy Apply')",
        "button:has-text('Solicitud sencilla')",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.count() and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(1500)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _fill_visible_fields(
    page, profile: UserProfile, cv_path, cv_text, job_title, company
) -> None:
    """Fill the currently visible modal step (best-effort)."""
    # Resume upload
    if cv_path:
        try:
            file_input = page.locator("input[type='file']").first
            if await file_input.count():
                await file_input.set_input_files(cv_path)
                await page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            pass

    # Text inputs that are empty: phone, etc.
    try:
        inputs = page.locator(
            ".jobs-easy-apply-content input[type='text'], "
            ".jobs-easy-apply-content input[type='tel'], "
            ".jobs-easy-apply-content input:not([type])"
        )
        count = await inputs.count()
        for i in range(min(count, 20)):
            el = inputs.nth(i)
            try:
                if (await el.input_value()).strip():
                    continue
                label = await _label_for(page, el)
                value = _value_for_label(label, profile)
                if value:
                    await el.fill(value)
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass

    # Free-text questions (textarea)
    try:
        areas = page.locator(".jobs-easy-apply-content textarea")
        for i in range(min(await areas.count(), 10)):
            el = areas.nth(i)
            try:
                if (await el.input_value()).strip():
                    continue
                label = await _label_for(page, el)
                if label and not is_sensitive_label(label):
                    ans = await answer_text_question(
                        label, profile, job_title, company, cv_text
                    )
                    if ans:
                        await el.fill(ans)
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass

    # Single-select dropdowns
    try:
        selects = page.locator(".jobs-easy-apply-content select")
        for i in range(min(await selects.count(), 10)):
            el = selects.nth(i)
            try:
                options = [o.strip() for o in await el.locator("option").all_inner_texts()]
                options = [o for o in options if o and "select" not in o.lower()]
                if not options:
                    continue
                label = await _label_for(page, el)
                if is_sensitive_label(label):
                    continue
                choice = await choose_option(label, options, profile, job_title)
                if choice:
                    await el.select_option(label=choice)
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass


async def _label_for(page, element) -> str:
    for attr in ("aria-label", "name", "placeholder"):
        try:
            val = await element.get_attribute(attr)
            if val:
                return val
        except Exception:  # noqa: BLE001
            continue
    return ""


def _value_for_label(label: str, profile: UserProfile) -> str:
    low = label.lower()
    if any(k in low for k in ("phone", "mobile", "tel")):
        return profile.phone
    if "email" in low or "correo" in low:
        return profile.email
    if "city" in low or "location" in low or "ubica" in low:
        return profile.location
    return ""


async def _has_submit(page) -> bool:
    for sel in ("button[aria-label*='Submit application']",
                "button:has-text('Submit application')",
                "button:has-text('Enviar solicitud')"):
        try:
            if await page.locator(sel).first.count():
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _click_submit(page) -> None:
    for sel in ("button[aria-label*='Submit application']",
                "button:has-text('Submit application')",
                "button:has-text('Enviar solicitud')"):
        try:
            btn = page.locator(sel).first
            if await btn.count():
                await btn.click()
                await page.wait_for_timeout(1500)
                return
        except Exception:  # noqa: BLE001
            continue


async def _click_next(page) -> bool:
    for sel in ("button[aria-label*='Continue to next step']",
                "button[aria-label*='Review']",
                "button:has-text('Next')",
                "button:has-text('Siguiente')",
                "button:has-text('Review')"):
        try:
            btn = page.locator(sel).first
            if await btn.count() and await btn.is_visible():
                await btn.click()
                return True
        except Exception:  # noqa: BLE001
            continue
    return False
