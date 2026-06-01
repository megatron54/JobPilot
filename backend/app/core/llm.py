"""LLM client abstraction. Default: Ollama (local, free)."""

import json
from typing import AsyncGenerator

import httpx

from app.core.config import settings


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

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{settings.llm_base_url}/api/generate", json=payload
        )
        resp.raise_for_status()
        return resp.json()["response"]


async def _stream_generate(payload: dict) -> AsyncGenerator[str, None]:
    """Yield tokens as they arrive from Ollama."""
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST", f"{settings.llm_base_url}/api/generate", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    data = json.loads(line)
                    if token := data.get("response"):
                        yield token
                    if data.get("done"):
                        break


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

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{settings.llm_base_url}/api/chat", json=payload
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


async def _stream_chat(payload: dict) -> AsyncGenerator[str, None]:
    """Yield tokens from chat streaming."""
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST", f"{settings.llm_base_url}/api/chat", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    data = json.loads(line)
                    if token := data.get("message", {}).get("content"):
                        yield token
                    if data.get("done"):
                        break
