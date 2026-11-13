"""Unit tests for the retrieval scoring helpers (no DB required)."""

import pytest

from app.services.retrieval import (
    _deduplicate_chunks,
    _keyword_boost,
    _has_strong_lexical_signal,
    _parse_query_words,
    _topic_overlap,
)


# ── _keyword_boost ────────────────────────────────────────────────


class TestKeywordBoost:
    def test_full_match(self) -> None:
        boost = _keyword_boost("quantum physics entanglement", "quantum physics")
        assert boost == pytest.approx(0.10)  # 2 words × 0.05

    def test_partial_match(self) -> None:
        boost = _keyword_boost("quantum mechanics overview", "quantum physics")
        assert boost == pytest.approx(0.05)  # 1 word

    def test_no_match(self) -> None:
        boost = _keyword_boost("biology and chemistry", "quantum physics")
        assert boost == pytest.approx(0.0)

    def test_short_query_words_ignored(self) -> None:
        # Words with len < 2 and stopwords are excluded from query words
        boost = _keyword_boost("a quantum is a thing", "a is quantum")
        assert boost == pytest.approx(0.05)  # only "quantum" counted

    def test_case_insensitive(self) -> None:
        boost = _keyword_boost("QUANTUM Physics", "quantum PHYSICS")
        assert boost == pytest.approx(0.10)


# ── _topic_overlap ────────────────────────────────────────────────


class TestTopicOverlap:
    def test_full_overlap(self) -> None:
        query_words = {"quantum", "physics", "particles"}
        text = "quantum physics studies particles"
        overlap = _topic_overlap(text, query_words)
        assert overlap == pytest.approx(1.0)

    def test_partial_overlap(self) -> None:
        query_words = {"quantum", "physics", "particles"}
        text = "quantum mechanics is different"
        overlap = _topic_overlap(text, query_words)
        assert overlap == pytest.approx(1 / 3)

    def test_no_overlap(self) -> None:
        query_words = {"quantum", "physics"}
        text = "biology and chemistry"
        overlap = _topic_overlap(text, query_words)
        assert overlap == pytest.approx(0.0)

    def test_empty_query_words(self) -> None:
        overlap = _topic_overlap("some text here", set())
        assert overlap == 0.0

    def test_short_words_excluded_from_text(self) -> None:
        # Words with len < 2 are excluded from text words by _signal_words
        query_words = {"a", "quantum"}
        text = "a quantum"
        overlap = _topic_overlap(text, query_words)
        # "a" is 1 char, excluded from text_words; only "quantum" matches
        assert overlap == pytest.approx(0.5)


class TestLexicalSignal:
    def test_detects_strong_match(self) -> None:
        query_words = {"digestive", "system", "breaks", "food", "nutrients"}
        text = "The digestive system breaks down food into nutrients."
        assert _has_strong_lexical_signal(text, query_words)

    def test_rejects_weak_match(self) -> None:
        query_words = {"digestive", "system", "breaks", "food", "nutrients"}
        text = "Human biology overview."
        assert not _has_strong_lexical_signal(text, query_words)


# ── _parse_query_words ────────────────────────────────────────────


class TestParseQueryWords:
    def test_basic_parsing(self) -> None:
        words = _parse_query_words("What is quantum physics")
        assert "quantum" in words
        assert "physics" in words
        assert "what" not in words

    def test_excludes_short_words(self) -> None:
        words = _parse_query_words("a is of quantum")
        assert "a" not in words
        assert "is" not in words
        assert "of" not in words
        assert "quantum" in words

    def test_lowercases(self) -> None:
        words = _parse_query_words("Quantum PHYSICS")
        assert "quantum" in words
        assert "physics" in words

    def test_empty_query(self) -> None:
        assert _parse_query_words("") == set()

    def test_strips_punctuation(self) -> None:
        words = _parse_query_words("What is Digestive Systems?")
        assert "digestive" in words
        assert "systems" in words

    def test_keeps_short_domain_terms_and_numbers(self) -> None:
        words = _parse_query_words("what to do on day 2?")
        assert "day" in words
        assert "2" in words


class TestConfidenceGuard:
    def test_day_number_query_can_overlap(self) -> None:
        query_words = _parse_query_words("what to do on day 2?")
        overlap = _topic_overlap("Day 2 — Fri, Dec 26: Jabarkhet Nature Reserve", query_words)
        assert overlap > 0.0


# ── _deduplicate_chunks ──────────────────────────────────────────


class TestDeduplicateChunks:
    def test_removes_exact_duplicates(self) -> None:
        chunks = [
            ({"content": "This is a chunk about physics.", "doc_id": "d1"}, 0.9),
            ({"content": "This is a chunk about physics.", "doc_id": "d2"}, 0.8),
        ]
        result = _deduplicate_chunks(chunks)
        assert len(result) == 1
        assert result[0][1] == 0.9  # keeps the first (higher scored)

    def test_keeps_unique_chunks(self) -> None:
        chunks = [
            ({"content": "Chunk about physics.", "doc_id": "d1"}, 0.9),
            ({"content": "Chunk about chemistry.", "doc_id": "d2"}, 0.8),
        ]
        result = _deduplicate_chunks(chunks)
        assert len(result) == 2

    def test_deduplicates_by_prefix(self) -> None:
        # Two chunks with same first 400 chars but different endings
        prefix = "A" * 400
        chunks = [
            ({"content": prefix + " ending one", "doc_id": "d1"}, 0.9),
            ({"content": prefix + " ending two", "doc_id": "d2"}, 0.8),
        ]
        result = _deduplicate_chunks(chunks)
        assert len(result) == 1

    def test_empty_input(self) -> None:
        assert _deduplicate_chunks([]) == []

    def test_preserves_order(self) -> None:
        chunks = [
            ({"content": "First chunk", "doc_id": "d1"}, 0.9),
            ({"content": "Second chunk", "doc_id": "d2"}, 0.7),
            ({"content": "Third chunk", "doc_id": "d3"}, 0.5),
        ]
        result = _deduplicate_chunks(chunks)
        assert [c[1] for c in result] == [0.9, 0.7, 0.5]
