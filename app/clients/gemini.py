import asyncio
import math
from typing import Any, AsyncIterator

from google import genai
from google.genai import errors, types

from app.config.env_config import get_settings


class GeminiClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self._embedding_model = settings.embedding_model
        self._embedding_output_dimensionality = settings.embedding_output_dimensionality
        self._generation_model = settings.free_tier_model
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

    @staticmethod
    def _l2_normalize(values: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            return values
        return [value / norm for value in values]

    def _normalize_if_needed(self, values: list[float]) -> list[float]:
        if (
            self._embedding_model == "gemini-embedding-2"
            and self._embedding_output_dimensionality != 3072
        ):
            return self._l2_normalize(values)
        return values

    async def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            result = None
            for attempt in range(5):
                try:
                    result = await self.client.aio.models.embed_content(
                        model=self._embedding_model,
                        contents=batch,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=self._embedding_output_dimensionality,
                        ),
                    )
                    break
                except errors.APIError as e:
                    if e.code == 429 and attempt < 4:
                        await asyncio.sleep(10.0)
                    else:
                        raise

            if result:
                embeddings.extend([self._normalize_if_needed(e.values) for e in result.embeddings])
        return embeddings

    async def embed_query(self, query: str) -> list[float]:
        result = None
        for attempt in range(5):
            try:
                result = await self.client.aio.models.embed_content(
                    model=self._embedding_model,
                    contents=query,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY",
                        output_dimensionality=self._embedding_output_dimensionality,
                    ),
                )
                break
            except errors.APIError as e:
                if e.code == 429 and attempt < 4:
                    await asyncio.sleep(10.0)
                else:
                    raise

        return self._normalize_if_needed(result.embeddings[0].values)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        response = await self.client.aio.models.generate_content(
            model=self._generation_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
                safety_settings=self._safety_settings,
            ),
        )
        return response.text

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        response = await self.client.aio.models.generate_content_stream(
            model=self._generation_model,
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
    ) -> str | AsyncIterator[str]:
        context = "\n\n".join(
            f"[{chunk['doc_name']} page {chunk.get('page', 'N/A')}]: {chunk['content']}"
            for chunk in context_chunks
        )

        system_prompt = """You are a helpful assistant that answers questions based only on the provided context.
Cite sources using [document_name page X] format.
If the answer is likely present but not explicit, infer cautiously.
Do not make up information."""

        if persona_config:
            style_config = persona_config.get("style_config", {})
            persona_rules = style_config.get("system_prompt")
            if not persona_rules:
                persona_rules = str(style_config)
            system_prompt = f"""{system_prompt}

After providing the factual answer, rewrite it in the style of {persona_config.get("name", "a helpful assistant")}.
{persona_rules}"""

        prompt = f"""Context:
{context}

Question: {query}

Answer:"""

        if stream:
            return self.generate_stream(prompt, system_prompt)
        return await self.generate(prompt, system_prompt)


gemini_client = GeminiClient()
