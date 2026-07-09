"""Tests for writing style rules and the drafter-reviewer refinement."""

from __future__ import annotations

import pytest

from app.automation import content
from app.automation.profile import UserProfile
from app.automation.writing_style import contains_cliches, has_em_dash

pytestmark = pytest.mark.asyncio


# --- style helpers (pure) ----------------------------------------------


def test_contains_cliches() -> None:
    found = contains_cliches("I am passionate about coding and a great fit")
    assert "passionate about" in found
    assert "great fit" in found


def test_contains_cliches_clean() -> None:
    assert contains_cliches("I built ML pipelines that cut latency 40%") == []


def test_has_em_dash() -> None:
    assert has_em_dash("This is a test \u2014 with em dash") is True
    assert has_em_dash("This uses -- double hyphen") is True
    assert has_em_dash("Clean sentence, no dash.") is False


# --- drafter-reviewer refinement ---------------------------------------


async def test_generate_cover_letter_no_refine(monkeypatch) -> None:
    calls = []

    async def fake_text(prompt, system="", **kw):
        calls.append(system)
        return "Draft cover letter."

    monkeypatch.setattr(content.llm, "generate_text", fake_text)
    out = await content.generate_cover_letter(
        UserProfile(name="Ada"), "Dev", "Acme", refine=False
    )
    assert out == "Draft cover letter."
    assert len(calls) == 1  # only the drafter


async def test_generate_cover_letter_with_refine(monkeypatch) -> None:
    outputs = ["Initial draft.", "Critique: too generic.", "Refined final letter."]
    idx = {"i": 0}

    async def fake_text(prompt, system="", **kw):
        out = outputs[idx["i"]]
        idx["i"] += 1
        return out

    monkeypatch.setattr(content.llm, "generate_text", fake_text)
    out = await content.generate_cover_letter(
        UserProfile(name="Ada"), "Dev", "Acme", description="desc", refine=True
    )
    assert out == "Refined final letter."
    assert idx["i"] == 3  # drafter + reviewer + reviser


async def test_refine_falls_back_to_draft_on_reviewer_error(monkeypatch) -> None:
    call = {"n": 0}

    async def fake_text(prompt, system="", **kw):
        call["n"] += 1
        if call["n"] == 1:
            return "Good draft."
        raise content.llm.LLMError("reviewer down")

    monkeypatch.setattr(content.llm, "generate_text", fake_text)
    out = await content.generate_cover_letter(
        UserProfile(name="Ada"), "Dev", "Acme", refine=True
    )
    assert out == "Good draft."


async def test_style_rules_in_prompt(monkeypatch) -> None:
    captured = {}

    async def fake_text(prompt, system="", **kw):
        captured["system"] = system
        return "letter"

    monkeypatch.setattr(content.llm, "generate_text", fake_text)
    await content.generate_cover_letter(UserProfile(), "Dev", "Acme")
    assert "No em-dashes" in captured["system"]
    assert "cliches" in captured["system"].lower()
