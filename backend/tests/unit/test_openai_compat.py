"""Unit tests for the OpenAI-compatible LLM client and provider routing."""

from __future__ import annotations

from typing import Any

import pytest

from app.llms import openai_compat
from app.llms.fallback import FallbackLLM
from app.llms.free import FreeTierGeminiLLM
from app.llms.groq import GroqLLM
from app.llms.openai_compat import OpenAICompatibleLLM
from app.llms.router import get_tier_llm_client


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self._body = body

    async def aread(self) -> bytes:
        return self._body

    def json(self) -> dict[str, Any]:
        return self._payload


def _client(**overrides: Any) -> OpenAICompatibleLLM:
    options = {
        "provider": "groq",
        "model_name": "openai/gpt-oss-120b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "gsk_test",
        "token_param": "max_completion_tokens",
    }
    options.update(overrides)
    return OpenAICompatibleLLM(**options)


def _patch_client(monkeypatch: pytest.MonkeyPatch, responses: list[FakeResponse]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        async def post(self, url: str, **kwargs: Any) -> FakeResponse:
            calls.append({"url": url, **kwargs})
            return responses.pop(0)

    monkeypatch.setattr(openai_compat.httpx, "AsyncClient", FakeAsyncClient)
    return calls


@pytest.mark.asyncio
async def test_groq_payload_uses_max_completion_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_client(
        monkeypatch,
        [FakeResponse(payload={"choices": [{"message": {"content": "hello"}}]})],
    )

    result = await _client()._generate("question", "system", temperature=0.2, max_tokens=256)

    assert result == "hello"
    request = calls[0]
    assert request["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer gsk_test"
    assert request["json"]["model"] == "openai/gpt-oss-120b"
    assert request["json"]["max_completion_tokens"] == 256
    assert "max_tokens" not in request["json"]
    assert request["json"]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "question"},
    ]


@pytest.mark.asyncio
async def test_reasoning_effort_is_only_sent_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_client(
        monkeypatch,
        [FakeResponse(payload={"choices": [{"message": {"content": "ok"}}]})],
    )
    await _client(reasoning_effort="low")._generate("q", "s")
    assert calls[0]["json"]["reasoning_effort"] == "low"

    calls = _patch_client(
        monkeypatch,
        [FakeResponse(payload={"choices": [{"message": {"content": "ok"}}]})],
    )
    await _client()._generate("q", "s")
    assert "reasoning_effort" not in calls[0]["json"]


@pytest.mark.asyncio
async def test_rate_limit_retries_after_sleeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(openai_compat.asyncio, "sleep", fake_sleep)
    _patch_client(
        monkeypatch,
        [
            FakeResponse(status_code=429, headers={"retry-after": "2"}),
            FakeResponse(payload={"choices": [{"message": {"content": "recovered"}}]}),
        ],
    )

    result = await _client()._generate("q", "s")

    assert result == "recovered"
    assert delays == [2.0]


@pytest.mark.asyncio
async def test_non_retryable_error_is_raised_with_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(
        monkeypatch,
        [FakeResponse(status_code=401, body=b'{"error": "invalid api key"}')],
    )

    with pytest.raises(RuntimeError, match="401.*invalid api key"):
        await _client()._generate("q", "s")


@pytest.mark.asyncio
async def test_missing_content_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, [FakeResponse(payload={"choices": [{"message": {}}]})])

    assert await _client()._generate("q", "s") == ""


@pytest.mark.asyncio
async def test_streaming_yields_delta_content(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        "data: [DONE]",
    ]

    class FakeStreamResponse:
        status_code = 200

        async def __aenter__(self) -> "FakeStreamResponse":
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        async def aread(self) -> bytes:
            return b""

        async def aiter_lines(self):
            for line in lines:
                yield line

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        def stream(self, method: str, url: str, **kwargs: Any) -> FakeStreamResponse:
            assert kwargs["json"]["stream"] is True
            return FakeStreamResponse()

    monkeypatch.setattr(openai_compat.httpx, "AsyncClient", FakeAsyncClient)

    chunks = [chunk async for chunk in _client()._generate_stream("q", "s")]

    assert chunks == ["Hel", "lo"]


# ── provider routing ──────────────────────────────────────────────


def test_free_tier_uses_groq_with_gemini_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FREE_TIER_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_test")
    monkeypatch.delenv("GROQ_MODEL", raising=False)

    client = get_tier_llm_client("free")

    assert isinstance(client, FallbackLLM)
    assert isinstance(client._primary, GroqLLM)
    assert isinstance(client._fallback, FreeTierGeminiLLM)
    assert client.provider == "groq"
    assert client.model_name == "openai/gpt-oss-120b"


def test_free_tier_uses_groq_alone_without_gemini_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FREE_TIER_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert isinstance(get_tier_llm_client("free"), GroqLLM)


def test_free_tier_falls_back_to_gemini_without_groq_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FREE_TIER_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    assert isinstance(get_tier_llm_client("free"), FreeTierGeminiLLM)


def test_unknown_tier_uses_the_free_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FREE_TIER_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_test")

    assert isinstance(get_tier_llm_client("unknown"), FallbackLLM)
