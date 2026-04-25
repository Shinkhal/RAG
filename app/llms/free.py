from typing import Any, AsyncIterator

from google import genai
from google.genai import types

from app.config.env_config import get_settings
from app.llms.base import BaseLLMClient
from app.llms.prompts import build_grounded_prompts
from app.schemas.query import ExternalSearchResult


class FreeTierGeminiLLM(BaseLLMClient):
    provider = "gemini"

    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = settings.free_tier_model
        self._safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_NONE",
            ),
        ]

    async def _generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
                safety_settings=self._safety_settings,
            ),
        )
        return response.text

    async def _generate_stream(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        response = await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
                safety_settings=self._safety_settings,
            ),
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def grounded_answer(
        self,
        query: str,
        context_chunks: list[dict[str, Any]],
        persona_config: dict[str, Any] | None = None,
        stream: bool = False,
        external_results: list[ExternalSearchResult] | None = None,
    ) -> str | AsyncIterator[str]:
        system_prompt, user_prompt = build_grounded_prompts(query, context_chunks, persona_config, external_results)
        if stream:
            return self._generate_stream(user_prompt, system_prompt)
        return await self._generate(user_prompt, system_prompt)
