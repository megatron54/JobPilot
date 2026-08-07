"""LLM client abstraction. Default: Ollama (local, free)."""

import json
import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings

logger = logging.getLogger("jobpilot.llm")


class LLMError(RuntimeError):
    """Raised when the LLM backend is unreachable or returns an unexpected
    response, so callers get a clear domain error instead of a raw
    KeyError/JSONDecodeError/httpx exception bubbling up as a 500.
    """


async def generate(prompt: str, system: str = "", stream: bool = False):
    """Generate a completion from the LLM."""
    payload = {
        "model": settings.llm_model,
        "prompt": prompt,
        "system": system,
        "stream": stream,
        "options": {"temperature": settings.llm_temperature},
    }

    if stream:
        return _stream_generate(payload)

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/api/generate", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach the LLM backend: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError("LLM backend returned an invalid response") from exc

    try:
        return data["response"]
    except KeyError as exc:
        raise LLMError("LLM backend response is missing 'response'") from exc


async def _stream_generate(payload: dict) -> AsyncGenerator[str, None]:
    """Yield tokens as they arrive from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream(
                "POST", f"{settings.llm_base_url}/api/generate", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping non-JSON line from Ollama stream")
                        continue
                    if token := data.get("response"):
                        yield token
                    if data.get("done"):
                        break
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach the LLM backend: {exc}") from exc


async def chat(messages: list[dict], stream: bool = False):
    """Chat completion (multi-turn). Messages: [{role, content}, ...]"""
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": settings.llm_temperature},
    }

    if stream:
        return _stream_chat(payload)

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{settings.llm_base_url}/api/chat", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach the LLM backend: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError("LLM backend returned an invalid response") from exc

    try:
        return data["message"]["content"]
    except KeyError as exc:
        raise LLMError("LLM backend response is missing 'message.content'") from exc


async def _stream_chat(payload: dict) -> AsyncGenerator[str, None]:
    """Yield tokens from chat streaming."""
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream(
                "POST", f"{settings.llm_base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping non-JSON line from Ollama stream")
                        continue
                    if token := data.get("message", {}).get("content"):
                        yield token
                    if data.get("done"):
                        break
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach the LLM backend: {exc}") from exc
