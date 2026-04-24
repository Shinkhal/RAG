from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


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
    ) -> str | AsyncIterator[str]:
        raise NotImplementedError
