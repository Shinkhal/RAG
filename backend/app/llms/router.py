from dataclasses import dataclass

from app.config.env_config import get_settings
from app.llms.base import BaseLLMClient
from app.llms.enterprise import EnterpriseTierAnthropicLLM
from app.llms.free import FreeTierGeminiLLM
from app.llms.pro import ProTierOpenAILLM


@dataclass(frozen=True)
class LLMTierConfig:
    tier: str
    provider: str
    generation_model: str
    persona_model: str
    queries_per_day: int
    max_tokens: int


def get_llm_config(subscription_tier: str) -> LLMTierConfig:
    settings = get_settings()
    tier = subscription_tier.lower()

    if tier == "pro":
        return LLMTierConfig(
            tier="pro",
            provider="openai",
            generation_model=settings.pro_tier_model,
            persona_model=settings.pro_tier_model,
            queries_per_day=500,
            max_tokens=4000,
        )
    if tier == "enterprise":
        return LLMTierConfig(
            tier="enterprise",
            provider="anthropic",
            generation_model=settings.enterprise_tier_model,
            persona_model=settings.enterprise_tier_model,
            queries_per_day=-1,
            max_tokens=8000,
        )
    return LLMTierConfig(
        tier="free",
        provider="gemini",
        generation_model=settings.free_tier_model,
        persona_model=settings.free_tier_model,
        queries_per_day=50,
        max_tokens=2000,
    )


def get_tier_llm_client(subscription_tier: str) -> BaseLLMClient:
    settings = get_settings()
    tier = subscription_tier.lower()

    if tier == "pro" and settings.openai_api_key:
        return ProTierOpenAILLM()
    if tier == "enterprise" and settings.anthropic_api_key:
        return EnterpriseTierAnthropicLLM()
    return FreeTierGeminiLLM()
