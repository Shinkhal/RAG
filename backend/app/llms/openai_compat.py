"""Client for providers exposing an OpenAI-style chat completions API.

Groq, OpenRouter, Cloudflare Workers AI, Ollama and many others all speak the
same ``POST /chat/completions`` protocol, so a single implementation can serve
all of them. Concrete providers only need to supply their base URL, key and
model name (see ``app/llms/groq.py``).
"""

import asyncio
import json
from typing import Any, AsyncIterator

import httpx

from app.llms.base import BaseLLMClient
from app.llms.prompts import build_grounded_prompts
from app.schemas.query import ExternalSearchResult
from app.utils.logger import logger

# Statuses worth retrying: rate limits, upstream capacity problems, transient
# server errors. Anything else (401, 400, 404) is a caller error and is raised
# immediately.
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def _retry_delay(response: httpx.Response | None, attempt: int, cap: float = 30.0) -> float:
    """Honor the provider's ``retry-after`` header, else back off exponentially."""
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), cap)
            except ValueError:
                pass
    return min(2.0**attempt, cap)


class OpenAICompatibleLLM(BaseLLMClient):
    provider = "openai-compatible"

    def __init__(
        self,
        *,
        provider: str,
        model_name: str,
        base_url: str,
        api_key: str,
        token_param: str = "max_tokens",
        reasoning_effort: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.provider = provider
        self.model_name = model_name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        # Reasoning models (e.g. gpt-oss) reject ``max_tokens``; others do not
        # accept ``max_completion_tokens``.
        self._token_param = token_param
        self._reasoning_effort = reasoning_effort or None
        self._timeout = timeout
        self._max_retries = max_retries

    @property
    def _endpoint(self) -> str:
        return f"{self._base_url}/chat/completions"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _payload(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            self._token_param: max_tokens,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        if stream:
            payload["stream"] = True
        return payload

    def _require_key(self) -> None:
        if not self._api_key:
            raise RuntimeError(f"{self.provider.upper()} API key is not configured")

    @staticmethod
    async def _error_body(response: httpx.Response) -> str:
        try:
            body = await response.aread()
        except Exception:  # pragma: no cover - best effort diagnostics
            return ""
        return body.decode("utf-8", errors="replace")[:500]

    async def _generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        self._require_key()
        payload = self._payload(prompt, system_prompt, temperature, max_tokens)

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.post(
                        self._endpoint, json=payload, headers=self._headers
                    )
                except httpx.TransportError as exc:
                    last_error = exc
                    if attempt >= self._max_retries:
                        raise
                    delay = _retry_delay(None, attempt)
                    logger.warning(
                        "%s request failed (%s); retrying in %.1fs",
                        self.provider,
                        type(exc).__name__,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                    delay = _retry_delay(response, attempt)
                    logger.warning(
                        "%s returned %d; retrying in %.1fs (attempt %d/%d)",
                        self.provider,
                        response.status_code,
                        delay,
                        attempt + 1,
                        self._max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code >= 400:
                    body = await self._error_body(response)
                    raise RuntimeError(
                        f"{self.provider} request failed with {response.status_code}: {body}"
                    )

                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise RuntimeError(f"{self.provider} returned no choices")
                return choices[0].get("message", {}).get("content") or ""

        raise RuntimeError(f"{self.provider} request failed") from last_error

    async def _generate_stream(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        self._require_key()
        payload = self._payload(
            prompt, system_prompt, temperature, max_tokens, stream=True
        )

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST", self._endpoint, json=payload, headers=self._headers
            ) as response:
                if response.status_code >= 400:
                    body = await self._error_body(response)
                    raise RuntimeError(
                        f"{self.provider} request failed with "
                        f"{response.status_code}: {body}"
                    )
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    content = (choices[0].get("delta") or {}).get("content")
                    if content:
                        yield content

    async def grounded_answer(
        self,
        query: str,
        context_chunks: list[dict[str, Any]],
        persona_config: dict[str, Any] | None = None,
        stream: bool = False,
        external_results: list[ExternalSearchResult] | None = None,
    ) -> str | AsyncIterator[str]:
        system_prompt, user_prompt = build_grounded_prompts(
            query, context_chunks, persona_config, external_results
        )
        if stream:
            return self._generate_stream(user_prompt, system_prompt)
        return await self._generate(user_prompt, system_prompt)
