"""Detect and classify form fields.

Two-stage classification: fast keyword heuristics first, then the LLM only for
fields the heuristics cannot confidently classify. Field extraction from the
live page is done by the filler; this module classifies the extracted metadata.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ...pipeline import llm
from ..field_mapping import FIELD_CATEGORIES

logger = logging.getLogger("jobpilot.autopilot.detector")


@dataclass
class FormField:
    """A field extracted from a form (before/after classification)."""

    selector: str
    label: str = ""
    name: str = ""
    placeholder: str = ""
    input_type: str = "text"        # text/email/tel/file/checkbox/select/textarea/radio
    required: bool = False
    options: list[str] = field(default_factory=list)
    category: str = "unknown"


# Keyword heuristics: category -> substrings that strongly imply it.
_HEURISTICS: list[tuple[str, tuple[str, ...]]] = [
    ("email", ("email", "e-mail", "correo")),
    ("phone", ("phone", "mobile", "tel", "tel\u00e9fono", "telefono")),
    ("first_name", ("first name", "firstname", "given name", "nombre")),
    ("last_name", ("last name", "lastname", "surname", "apellido")),
    ("full_name", ("full name", "your name", "name")),
    ("linkedin_url", ("linkedin",)),
    ("resume_upload", ("resume", "cv", "curriculum")),
    ("cover_letter", ("cover letter", "carta")),
    ("location", ("location", "address", "ubicaci\u00f3n", "ubicacion")),
    ("city", ("city", "ciudad")),
    ("current_title", ("current title", "job title", "puesto")),
    ("current_company", ("current company", "employer", "empresa")),
    ("experience_years", ("years of experience", "years experience", "a\u00f1os de experiencia")),
    ("website", ("website", "portfolio", "url")),
    ("salary_expectation", ("salary", "compensation", "salario")),
    ("work_authorization", ("authorization", "authorized to work", "visa", "sponsorship")),
    ("start_date", ("start date", "availability", "fecha de inicio")),
    ("consent_checkbox", ("consent", "agree", "privacy", "gdpr", "acepto")),
]


def classify_heuristic(form_field: FormField) -> str:
    """Best-effort keyword classification. Returns 'unknown' if unsure."""
    if form_field.input_type == "file":
        return "resume_upload"
    haystack = " ".join(
        [form_field.label, form_field.name, form_field.placeholder]
    ).lower()
    if not haystack.strip():
        return "unknown"
    for category, keywords in _HEURISTICS:
        if any(_kw_match(k, haystack) for k in keywords):
            return category
    # A long free-text area with no match is likely a custom question.
    if form_field.input_type == "textarea":
        return "custom_question"
    return "unknown"


def _kw_match(keyword: str, haystack: str) -> bool:
    """Word-boundary match to avoid false positives (e.g. 'tel' in 'tell')."""
    return re.search(rf"(?<![a-z]){re.escape(keyword)}(?![a-z])", haystack) is not None


async def classify_with_llm(fields: list[FormField]) -> None:
    """Classify still-unknown fields with the LLM, in place."""
    unknown = [f for f in fields if f.category == "unknown"]
    if not unknown:
        return

    listing = "\n".join(
        f"{i}. label='{f.label}' name='{f.name}' type='{f.input_type}'"
        for i, f in enumerate(unknown)
    )
    categories = ", ".join(sorted(FIELD_CATEGORIES))
    schema = {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "category": {"type": "string"},
                    },
                    "required": ["index", "category"],
                },
            }
        },
        "required": ["fields"],
    }
    prompt = (
        f"Classify each form field into exactly one category from this list:\n"
        f"{categories}\n\nFIELDS:\n{listing}\n\n"
        "Return JSON {fields: [{index, category}]}."
    )
    try:
        data = await llm.generate_json(prompt=prompt, schema=schema)
    except llm.LLMError as exc:
        logger.info("LLM field classification failed: %s", exc)
        return

    for item in data.get("fields", []):
        try:
            idx = int(item["index"])
            cat = str(item["category"])
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= idx < len(unknown) and cat in FIELD_CATEGORIES:
            unknown[idx].category = cat


async def classify_fields(fields: list[FormField], use_llm: bool = True) -> list[FormField]:
    """Classify all fields: heuristics first, LLM for the remainder."""
    for f in fields:
        if f.category == "unknown":
            f.category = classify_heuristic(f)
    if use_llm:
        await classify_with_llm(fields)
    return fields
