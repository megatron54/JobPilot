"""Ollama client for the Autopilot pipeline.

Separate from the main app's LLM client so it can use automation-specific
settings (score vs generation models) and structured JSON output for fast,
deterministic scoring. See docs/AUTOPILOT_PLAN.md section 8.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger("jobpilot.autopilot.llm")


class LLMError(Exception):
    """Raised when the LLM call fails."""


async def generate_json(
    prompt: str,
    system: str = "",
    schema: dict[str, Any] | None = None,
    model: str | None = None,
    timeout_s: float = 60.0,
) -> dict:
    """Generate a structured JSON response (deterministic, capped output).

    Uses Ollama's `format` parameter to force valid JSON. Temperature 0 for
    determinism. Returns the parsed dict, or raises LLMError.
    """
    payload: dict[str, Any] = {
        "model": model or settings.llm_score_model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 400},
    }
    payload["format"] = schema if schema else "json"

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/api/generate", json=payload
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMError(f"LLM returned invalid JSON: {exc}") from exc


async def generate_text(
    prompt: str,
    system: str = "",
    model: str | None = None,
    temperature: float | None = None,
    timeout_s: float = 180.0,
) -> str:
    """Generate free-form text (for content generation)."""
    payload: dict[str, Any] = {
        "model": model or settings.llm_gen_model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": settings.llm_temperature if temperature is None else temperature
        },
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/api/generate", json=payload
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc


async def is_available() -> bool:
    """Check whether Ollama is reachable."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.llm_base_url}/api/tags")
            return resp.status_code == 200
    except httpx.HTTPError:
        return False
