from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from app.schemas.query import ExternalSearchResult


class BaseLLMClient(ABC):
    provider: str
    model_name: str

    @abstractmethod
    async def grounded_answer(
        self,
        query: str,
        context_chunks: list[dict[str, Any]],
        persona_config: dict[str, Any] | None = None,
        stream: bool = False,
        external_results: list[ExternalSearchResult] | None = None,
    ) -> str | AsyncIterator[str]:
        raise NotImplementedError

    @abstractmethod
    async def _generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def _generate_stream(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
