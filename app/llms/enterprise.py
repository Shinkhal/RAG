from typing import Any, AsyncIterator

import httpx

from app.config.env_config import get_settings
from app.llms.base import BaseLLMClient
from app.llms.prompts import build_grounded_prompts


class EnterpriseTierAnthropicLLM(BaseLLMClient):
    provider = "anthropic"

    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = settings.enterprise_tier_model
        self._api_key = settings.anthropic_api_key
        self._base_url = settings.anthropic_base_url.rstrip("/")

    async def _generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

        payload = {
            "model": self.model_name,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/messages", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
            text_blocks = [
                block["text"] for block in data.get("content", []) if block.get("type") == "text"
            ]
            return "".join(text_blocks)

    async def _generate_stream(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        # Fallback to non-streaming call to keep a consistent async token interface.
        answer = await self._generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield answer

    async def grounded_answer(
        self,
        query: str,
        context_chunks: list[dict[str, Any]],
        persona_config: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        system_prompt, user_prompt = build_grounded_prompts(query, context_chunks, persona_config)
        if stream:
            return self._generate_stream(user_prompt, system_prompt)
        return await self._generate(user_prompt, system_prompt)
