"""Tests for form-field classification (heuristics + LLM stage)."""

from __future__ import annotations

import pytest

from app.automation.executor.form_filler import detector
from app.automation.executor.form_filler.detector import (
    FormField,
    classify_fields,
    classify_heuristic,
)

pytestmark = pytest.mark.asyncio


def test_heuristic_email() -> None:
    f = FormField(selector="x", label="Email address", input_type="email")
    assert classify_heuristic(f) == "email"


def test_heuristic_file_is_resume() -> None:
    f = FormField(selector="x", label="Upload", input_type="file")
    assert classify_heuristic(f) == "resume_upload"


def test_heuristic_phone() -> None:
    f = FormField(selector="x", name="phone_number")
    assert classify_heuristic(f) == "phone"


def test_heuristic_linkedin() -> None:
    f = FormField(selector="x", label="LinkedIn Profile")
    assert classify_heuristic(f) == "linkedin_url"


def test_heuristic_textarea_is_custom_question() -> None:
    f = FormField(selector="x", label="Tell us why", input_type="textarea")
    assert classify_heuristic(f) == "custom_question"


def test_heuristic_unknown() -> None:
    f = FormField(selector="x", label="Mystery field", input_type="text")
    assert classify_heuristic(f) == "unknown"


async def test_classify_fields_uses_llm_for_unknown(monkeypatch) -> None:
    fields = [
        FormField(selector="1", label="Email", input_type="email"),
        FormField(selector="2", label="Tu disponibilidad horaria", input_type="text"),
    ]

    async def fake_json(**kwargs):
        # The LLM classifies the single remaining unknown (index 0 of unknowns).
        return {"fields": [{"index": 0, "category": "start_date"}]}

    monkeypatch.setattr(detector.llm, "generate_json", fake_json)
    await classify_fields(fields, use_llm=True)

    assert fields[0].category == "email"        # heuristic
    assert fields[1].category == "start_date"   # llm


async def test_classify_fields_no_llm(monkeypatch) -> None:
    fields = [FormField(selector="1", label="Email", input_type="email")]
    await classify_fields(fields, use_llm=False)
    assert fields[0].category == "email"
