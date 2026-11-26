"""Provider fallback wrapper.

The free tier uses a free hosted model, so it must survive that provider being
rate limited, out of tokens, or temporarily unavailable. ``FallbackLLM`` tries
the primary client and transparently retries with a secondary client, updating
``provider``/``model_name`` so response metadata reflects who answered.
"""

from typing import Any, AsyncIterator

from app.llms.base import BaseLLMClient
from app.llms.prompts import build_grounded_prompts
from app.schemas.query import ExternalSearchResult
from app.utils.logger import logger


class FallbackLLM(BaseLLMClient):
    def __init__(self, primary: BaseLLMClient, fallback: BaseLLMClient) -> None:
        self._primary = primary
        self._fallback = fallback
        self.provider = primary.provider
        self.model_name = primary.model_name

    def _use(self, client: BaseLLMClient) -> None:
        self.provider = client.provider
        self.model_name = client.model_name

    def _log_fallback(self, error: Exception) -> None:
        logger.warning(
            "%s failed (%s); falling back to %s/%s",
            self._primary.provider,
            type(error).__name__,
            self._fallback.provider,
            self._fallback.model_name,
            exc_info=True,
        )

    async def _generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        try:
            answer = await self._primary._generate(
                prompt, system_prompt, temperature, max_tokens
            )
            self._use(self._primary)
            return answer
        except Exception as exc:
            self._log_fallback(exc)

        self._use(self._fallback)
        return await self._fallback._generate(
            prompt, system_prompt, temperature, max_tokens
        )

    async def _generate_stream(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        emitted = False
        try:
            async for token in self._primary._generate_stream(
                prompt, system_prompt, temperature, max_tokens
            ):
                if not emitted:
                    self._use(self._primary)
                    emitted = True
                yield token
            return
        except Exception as exc:
            # Tokens already reached the client; restarting would duplicate the
            # answer, so surface the error instead of falling back mid-stream.
            if emitted:
                raise
            self._log_fallback(exc)

        self._use(self._fallback)
        async for token in self._fallback._generate_stream(
            prompt, system_prompt, temperature, max_tokens
        ):
            yield token

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

        if not stream:
            return await self._generate(user_prompt, system_prompt)

        # Prime the stream so a failing primary provider is detected before the
        # caller reads provider/model metadata, and before any token is sent.
        stream_iterator = self._generate_stream(user_prompt, system_prompt)
        try:
            first_token = await stream_iterator.__anext__()
        except StopAsyncIteration:
            return _empty_stream()

        return _prepend(first_token, stream_iterator)


async def _prepend(first: str, rest: AsyncIterator[str]) -> AsyncIterator[str]:
    yield first
    async for token in rest:
        yield token


async def _empty_stream() -> AsyncIterator[str]:
    return
    yield ""  # pragma: no cover - makes the function an async generator
