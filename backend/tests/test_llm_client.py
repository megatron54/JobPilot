"""Tests for app/core/llm.py error handling (LLMError instead of raw
httpx/JSON exceptions bubbling up as opaque 500s)."""

from __future__ import annotations

import httpx
import pytest

from app.core import llm


@pytest.mark.asyncio
async def test_generate_raises_llm_error_on_connection_failure(monkeypatch):
    async def fake_post(self, url, json):
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(llm.LLMError):
        await llm.generate("hello")


@pytest.mark.asyncio
async def test_chat_raises_llm_error_on_connection_failure(monkeypatch):
    async def fake_post(self, url, json):
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(llm.LLMError):
        await llm.chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_generate_raises_llm_error_on_missing_response_key(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"unexpected": "shape"}

    async def fake_post(self, url, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(llm.LLMError):
        await llm.generate("hello")


@pytest.mark.asyncio
async def test_generate_returns_response_text_on_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "Hello, world!"}

    async def fake_post(self, url, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await llm.generate("hello")
    assert result == "Hello, world!"
