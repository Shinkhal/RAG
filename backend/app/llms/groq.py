"""Groq free-tier generation client."""

from app.config.env_config import get_settings
from app.llms.openai_compat import OpenAICompatibleLLM


class GroqLLM(OpenAICompatibleLLM):
    """Groq exposes an OpenAI-compatible chat completions endpoint.

    Groq's free plan is generous on requests (1,000/day for gpt-oss models) but
    tight on tokens, so the client retries ``429`` responses using Groq's
    ``retry-after`` header instead of failing the query outright.
    """

    provider = "groq"

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(
            provider="groq",
            model_name=settings.groq_model,
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key,
            # gpt-oss rejects the legacy ``max_tokens`` parameter.
            token_param="max_completion_tokens",
            reasoning_effort=settings.groq_reasoning_effort or None,
        )
