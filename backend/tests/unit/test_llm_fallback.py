"""Tests for the free-tier provider fallback wrapper."""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from app.llms.fallback import FallbackLLM

CHUNKS = [
    {
        "content": "Hybrid search combines dense embeddings with BM25.",
        "doc_name": "rag.md",
        "page": 1,
    }
]


class FakeClient:
    def __init__(self, provider: str, model_name: str, tokens: list[str]) -> None:
        self.provider = provider
        self.model_name = model_name
        self.tokens = tokens
        self.calls = 0

    async def _generate(self, *args: Any, **kwargs: Any) -> str:
        self.calls += 1
        return "".join(self.tokens)

    async def _generate_stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[str]:
        self.calls += 1
        for token in self.tokens:
            yield token


class FailingClient(FakeClient):
    def __init__(self, provider: str, model_name: str, error: Exception) -> None:
        super().__init__(provider, model_name, [])
        self.error = error

    async def _generate(self, *args: Any, **kwargs: Any) -> str:
        self.calls += 1
        raise self.error

    async def _generate_stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[str]:
        self.calls += 1
        raise self.error
        yield ""  # pragma: no cover


class PartialClient(FakeClient):
    """Yields one token, then fails mid-stream."""

    async def _generate_stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[str]:
        self.calls += 1
        yield "partial"
        raise RuntimeError("connection dropped")


def _groq(tokens: list[str] | None = None) -> FakeClient:
    return FakeClient("groq", "openai/gpt-oss-120b", tokens or ["answer"])


def _gemini(tokens: list[str] | None = None) -> FakeClient:
    return FakeClient("gemini", "gemini-3.5-flash-lite", tokens or ["gemini", "answer"])


@pytest.mark.asyncio
async def test_uses_primary_when_it_succeeds() -> None:
    primary, fallback = _groq(), _gemini()
    llm = FallbackLLM(primary, fallback)

    answer = await llm.grounded_answer("q", CHUNKS)

    assert answer == "answer"
    assert llm.provider == "groq"
    assert llm.model_name == "openai/gpt-oss-120b"
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_falls_back_when_primary_fails() -> None:
    primary = FailingClient("groq", "openai/gpt-oss-120b", RuntimeError("429"))
    fallback = _gemini()
    llm = FallbackLLM(primary, fallback)

    answer = await llm.grounded_answer("q", CHUNKS)

    assert answer == "geminianswer"
    assert llm.provider == "gemini"
    assert llm.model_name == "gemini-3.5-flash-lite"
    assert primary.calls == 1
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_stream_falls_back_when_primary_fails_before_first_token() -> None:
    primary = FailingClient("groq", "openai/gpt-oss-120b", RuntimeError("503"))
    fallback = _gemini(["Gemini", " works"])
    llm = FallbackLLM(primary, fallback)

    stream = await llm.grounded_answer("q", CHUNKS, stream=True)

    # Metadata must already reflect the fallback before any token is consumed.
    assert llm.provider == "gemini"

    tokens = [token async for token in stream]

    assert tokens == ["Gemini", " works"]
    assert llm.provider == "gemini"


@pytest.mark.asyncio
async def test_stream_does_not_fall_back_after_tokens_were_emitted() -> None:
    primary = PartialClient("groq", "openai/gpt-oss-120b", [])
    fallback = _gemini()
    llm = FallbackLLM(primary, fallback)

    stream = await llm.grounded_answer("q", CHUNKS, stream=True)

    received: list[str] = []
    with pytest.raises(RuntimeError, match="connection dropped"):
        async for token in stream:
            received.append(token)

    assert received == ["partial"]
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_stream_metadata_reports_primary_when_healthy() -> None:
    primary = _groq(["a", "b"])
    fallback = _gemini()
    llm = FallbackLLM(primary, fallback)

    stream = await llm.grounded_answer("q", CHUNKS, stream=True)

    assert llm.provider == "groq"
    assert [token async for token in stream] == ["a", "b"]
    assert fallback.calls == 0
