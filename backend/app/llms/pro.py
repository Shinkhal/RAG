"""Pro-tier OpenAI generation client."""

from app.config.env_config import get_settings
from app.llms.openai_compat import OpenAICompatibleLLM


class ProTierOpenAILLM(OpenAICompatibleLLM):
    provider = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(
            provider="openai",
            model_name=settings.pro_tier_model,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )
