"""Unit tests for the LLM prompt building and routing logic."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.llms.prompts import _build_context, _render_style_rules, build_grounded_prompts
from app.llms.router import LLMTierConfig, get_llm_config
from app.schemas.query import ExternalSearchResult
from app.services.generation import generate_answer


# ── _render_style_rules ───────────────────────────────────────────


class TestRenderStyleRules:
    def test_uses_system_prompt_if_present(self) -> None:
        config = {"system_prompt": "You are Einstein. Be thoughtful."}
        result = _render_style_rules(config)
        assert result == "You are Einstein. Be thoughtful."

    def test_falls_back_to_structured_fields(self) -> None:
        config = {
            "tone": "calm, reflective",
            "voice": "philosophical",
            "rules": ["Use analogies", "Be concise"],
            "do": ["Guide step by step"],
            "dont": ["Do not exaggerate"],
        }
        result = _render_style_rules(config)
        assert "tone: calm, reflective" in result
        assert "voice: philosophical" in result
        assert "- Use analogies" in result
        assert "- Guide step by step" in result
        assert "- Do not exaggerate" in result

    def test_formatting_section(self) -> None:
        config = {
            "formatting": {
                "style": "paragraph",
                "use_analogies": True,
            }
        }
        result = _render_style_rules(config)
        assert "formatting:" in result
        assert "- style: paragraph" in result

    def test_empty_config(self) -> None:
        result = _render_style_rules({})
        assert result == ""

    def test_prefers_system_prompt_over_structured(self) -> None:
        config = {
            "system_prompt": "Use this prompt.",
            "tone": "should be ignored",
        }
        result = _render_style_rules(config)
        assert result == "Use this prompt."
        assert "tone" not in result


# ── _build_context ────────────────────────────────────────────────


class TestBuildContext:
    def test_empty_chunks(self) -> None:
        result = _build_context([], "test query")
        assert "No relevant documents found" in result

    def test_missing_doc_name_falls_back_to_doc_id(self) -> None:
        chunks = [
            {"content": "quantum data", "doc_id": "doc-123", "chunk_idx": 7, "page": 2},
        ]
        result = _build_context(chunks, "quantum")
        assert "doc-123" in result
        assert "#7" in result

    def test_categorizes_relevant_vs_weak(self) -> None:
        chunks = [
            {"content": "quantum physics is fascinating", "doc_name": "doc1", "page": 1, "chunk_id": 0},
            {"content": "biology and cells overview", "doc_name": "doc2", "page": 3, "chunk_id": 1},
        ]
        result = _build_context(chunks, "quantum physics")
        assert "RELEVANT CONTEXT" in result
        assert "WEAK CONTEXT" in result

    def test_all_relevant(self) -> None:
        chunks = [
            {"content": "quantum physics particles", "doc_name": "doc1", "page": 1, "chunk_id": 0},
        ]
        result = _build_context(chunks, "quantum physics")
        assert "RELEVANT CONTEXT" in result
        assert "WEAK CONTEXT" not in result

    def test_includes_doc_metadata_in_context(self) -> None:
        chunks = [
            {"content": "quantum data", "doc_name": "report.pdf", "page": 42, "chunk_id": 5},
        ]
        result = _build_context(chunks, "quantum")
        assert "report.pdf" in result
        assert "42" in result


# ── build_grounded_prompts ────────────────────────────────────────


class TestBuildGroundedPrompts:
    def test_basic_prompt_structure(self) -> None:
        system, user = build_grounded_prompts(
            query="What is gravity?",
            context_chunks=[{"content": "Gravity is a force", "doc_name": "physics.pdf", "page": 1, "chunk_id": 0}],
        )
        assert "ONLY use the provided context" in system
        assert "What is gravity?" in user
        assert "Context:" in user

    def test_persona_adds_transformation_rules(self) -> None:
        persona = {
            "name": "Einstein",
            "intensity": 0.8,
            "style_config": {"system_prompt": "Speak like Einstein"},
        }
        system, user = build_grounded_prompts(
            query="What is gravity?",
            context_chunks=[{"content": "Gravity pulls objects", "doc_name": "doc.pdf", "page": 1, "chunk_id": 0}],
            persona_config=persona,
        )
        assert "PERSONA TRANSFORMATION" in system
        assert "Einstein" in system
        assert "0.80" in system
        assert "Speak like Einstein" in system

    def test_no_persona_no_transformation_section(self) -> None:
        system, _ = build_grounded_prompts(
            query="What is gravity?",
            context_chunks=[],
        )
        assert "PERSONA TRANSFORMATION" not in system

    def test_external_results_add_section(self) -> None:
        external = [
            ExternalSearchResult(title="Wiki", url="https://example.com", snippet="Info")
        ]
        system, _ = build_grounded_prompts(
            query="test",
            context_chunks=[],
            external_results=external,
        )
        assert "EXTERNAL KNOWLEDGE" in system


class TestGenerateAnswer:
    @pytest.mark.asyncio
    async def test_uses_llm_when_external_results_exist_even_if_low_confidence(self, monkeypatch) -> None:
        llm_client = SimpleNamespace(
            provider="gemini",
            model_name="gemini-test",
            grounded_answer=AsyncMock(return_value="Digestive system answer"),
        )
        monkeypatch.setattr("app.services.generation.get_tier_llm_client", lambda _tier: llm_client)

        chunks = [
            (
                {
                    "content": "Digestive system breaks down food.",
                    "doc_id": "doc-1",
                    "metadata": {"filename": "biology.pdf", "page": 1},
                },
                0.72,
            )
        ]
        external = [
            ExternalSearchResult(
                title="Digestive system",
                url="https://example.com/digestive",
                snippet="The digestive system breaks down food into nutrients.",
            )
        ]

        answer, sources, llm_details, returned_external = await generate_answer(
            query="What is Digestive Systems?",
            chunks=chunks,
            force_general=False,
            external_results=external,
        )

        assert answer == "Digestive system answer"
        assert len(sources) == 1
        assert llm_details["model"] == "gemini-test"
        assert returned_external == external
        llm_client.grounded_answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_force_general_returns_canned_fallback(self, monkeypatch) -> None:
        llm_client = SimpleNamespace(
            provider="gemini",
            model_name="gemini-test",
            grounded_answer=AsyncMock(),
        )
        monkeypatch.setattr("app.services.generation.get_tier_llm_client", lambda _tier: llm_client)

        answer, sources, _, returned_external = await generate_answer(
            query="Unknown topic",
            chunks=[],
            force_general=True,
            external_results=[],
        )

        assert answer == "I don't have enough information in the provided documents about this topic."
        assert sources == []
        assert returned_external == []
        llm_client.grounded_answer.assert_not_awaited()


# ── get_llm_config ────────────────────────────────────────────────


class TestGetLlmConfig:
    def test_free_tier_defaults(self) -> None:
        config = get_llm_config("free")
        assert config.tier == "free"
        assert config.provider == "gemini"
        assert config.queries_per_day == 50
        assert config.max_tokens == 2000

    def test_pro_tier(self) -> None:
        config = get_llm_config("pro")
        assert config.tier == "pro"
        assert config.provider == "openai"
        assert config.queries_per_day == 500

    def test_enterprise_tier(self) -> None:
        config = get_llm_config("enterprise")
        assert config.tier == "enterprise"
        assert config.provider == "anthropic"
        assert config.queries_per_day == -1

    def test_unknown_tier_falls_back_to_free(self) -> None:
        config = get_llm_config("unknown_tier")
        assert config.tier == "free"
        assert config.provider == "gemini"

    def test_case_insensitive(self) -> None:
        config = get_llm_config("PRO")
        assert config.tier == "pro"

    def test_config_is_frozen_dataclass(self) -> None:
        config = get_llm_config("free")
        with pytest.raises((AttributeError, TypeError)):
            config.tier = "pro"  # type: ignore[misc]
