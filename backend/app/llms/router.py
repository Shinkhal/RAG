from dataclasses import dataclass

from app.config.env_config import get_settings
from app.llms.base import BaseLLMClient
from app.llms.enterprise import EnterpriseTierAnthropicLLM
from app.llms.fallback import FallbackLLM
from app.llms.free import FreeTierGeminiLLM
from app.llms.groq import GroqLLM
from app.llms.pro import ProTierOpenAILLM


@dataclass(frozen=True)
class LLMTierConfig:
    tier: str
    provider: str
    generation_model: str
    persona_model: str
    queries_per_day: int
    max_tokens: int


def _free_tier_provider() -> str:
    """Resolve the effective free-tier provider.

    Groq is preferred when configured, but a missing key must never take the
    free tier offline: fall back to Gemini instead of failing every query.
    """
    settings = get_settings()
    if settings.free_tier_provider == "groq" and settings.groq_api_key:
        return "groq"
    return "gemini"


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

    provider = _free_tier_provider()
    model = settings.groq_model if provider == "groq" else settings.free_tier_model
    return LLMTierConfig(
        tier="free",
        provider=provider,
        generation_model=model,
        persona_model=model,
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
    if _free_tier_provider() == "groq":
        # Gemini (free tier) is the safety net when Groq is rate limited or
        # down. Without a Gemini key there is nothing to fall back to.
        if settings.gemini_api_key:
            return FallbackLLM(GroqLLM(), FreeTierGeminiLLM())
        return GroqLLM()
    return FreeTierGeminiLLM()
