"""Universal external form filler.

Extracts fields from any application page, classifies them (heuristics + LLM),
maps known fields from the profile, generates answers for custom questions, and
fills the form in a visible browser. Pauses before submit for user review.
Detects CAPTCHAs / account-creation walls and hands off to the user.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ...profile import UserProfile
from ..answers import answer_text_question
from .detector import FormField, classify_fields
from ..field_mapping import value_for_field

logger = logging.getLogger("jobpilot.autopilot.filler")


@dataclass
class FillOutcome:
    status: str            # filled_needs_review / captcha / account_required / failed / no_form
    detail: str = ""
    fields_filled: int = 0
    custom_questions: int = 0


async def fill_external_form(
    page,
    url: str,
    profile: UserProfile,
    cv_path: str | None = None,
    cv_text: str = "",
    job_title: str = "",
    company: str = "",
    extra_values: dict | None = None,
) -> FillOutcome:
    """Navigate to an external application URL and fill it. Never submits."""
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        if await _has_captcha(page):
            return FillOutcome("captcha", "CAPTCHA detected - complete it manually")
        if await _needs_account(page):
            return FillOutcome("account_required", "Account creation required - do it manually")

        fields = await _extract_fields(page)
        if not fields:
            return FillOutcome("no_form", "No form fields found - apply manually")

        await classify_fields(fields, use_llm=True)
        filled, custom = await _fill_fields(
            page, fields, profile, cv_path, cv_text, job_title, company, extra_values or {}
        )
        return FillOutcome(
            "filled_needs_review",
            "Form filled - review and submit in the browser",
            fields_filled=filled,
            custom_questions=custom,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("External form fill failed for %s", url)
        return FillOutcome("failed", str(exc))


async def _extract_fields(page) -> list[FormField]:
    """Extract field metadata from inputs/textareas/selects on the page."""
    handles = await page.locator(
        "form input, form textarea, form select"
    ).element_handles()
    if not handles:
        handles = await page.locator("input, textarea, select").element_handles()

    fields: list[FormField] = []
    for i, h in enumerate(handles):
        try:
            tag = (await h.evaluate("el => el.tagName")).lower()
            input_type = (await h.get_attribute("type") or
                          ("textarea" if tag == "textarea" else
                           "select" if tag == "select" else "text")).lower()
            if input_type in ("hidden", "submit", "button"):
                continue
            name = await h.get_attribute("name") or ""
            placeholder = await h.get_attribute("placeholder") or ""
            aria = await h.get_attribute("aria-label") or ""
            required = await h.get_attribute("required") is not None
            label = aria or await _label_text(page, h) or placeholder

            options: list[str] = []
            if input_type == "select":
                try:
                    options = [
                        o.strip()
                        for o in await h.locator("option").all_inner_texts()  # type: ignore
                    ]
                except Exception:  # noqa: BLE001
                    options = []

            fields.append(FormField(
                selector=f"__handle_{i}",
                label=label,
                name=name,
                placeholder=placeholder,
                input_type=input_type,
                required=required,
                options=options,
            ))
            fields[-1].__dict__["_handle"] = h
        except Exception:  # noqa: BLE001
            continue
    return fields


async def _label_text(page, handle) -> str:
    try:
        return await handle.evaluate(
            """el => {
                if (el.id) {
                    const l = document.getElementById(el.id)
                        ? document.querySelector('label[for="' + CSS.escape(el.id) + '"]')
                        : null;
                    if (l) return l.innerText;
                }
                const p = el.closest('label');
                return p ? p.innerText : '';
            }"""
        )
    except Exception:  # noqa: BLE001
        return ""


async def _fill_fields(
    page, fields, profile, cv_path, cv_text, job_title, company, extra
) -> tuple[int, int]:
    filled = 0
    custom = 0
    for f in fields:
        handle = f.__dict__.get("_handle")
        if handle is None:
            continue
        try:
            if f.category == "resume_upload" and cv_path:
                await handle.set_input_files(cv_path)
                filled += 1
            elif f.category == "consent_checkbox":
                try:
                    await handle.check()
                    filled += 1
                except Exception:  # noqa: BLE001
                    pass
            elif f.category == "custom_question":
                ans = await answer_text_question(
                    f.label, profile, job_title, company, cv_text
                )
                if ans:
                    await handle.fill(ans)
                    filled += 1
                    custom += 1
            elif f.category != "unknown":
                value = value_for_field(f.category, profile, extra)
                if value:
                    await handle.fill(value)
                    filled += 1
        except Exception:  # noqa: BLE001
            continue
    return filled, custom


async def _has_captcha(page) -> bool:
    for sel in ("iframe[src*='recaptcha']", "iframe[src*='hcaptcha']",
                "div.g-recaptcha", "[class*='captcha']"):
        try:
            if await page.locator(sel).first.count():
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _needs_account(page) -> bool:
    try:
        body = (await page.locator("body").inner_text()).lower()
    except Exception:  # noqa: BLE001
        return False
    signals = ("create an account", "sign up to apply", "create account to apply",
               "crea una cuenta", "regístrate para")
    return any(s in body for s in signals)
