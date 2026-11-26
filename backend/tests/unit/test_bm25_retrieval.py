import pytest
from app.services.retrieval import (
    _bm25_score,
    _reciprocal_rank_fusion,
)


class TestBM25Score:
    def test_returns_scores_for_chunks(self):
        chunks = [
            ({"content": "the cat sat on the mat"}, 0.8),
            ({"content": "the dog ran in the park"}, 0.7),
            ({"content": "cat and dog are animals"}, 0.6),
        ]
        scores = _bm25_score("cat", chunks)
        assert len(scores) == 3
        assert all(s >= 0 for s in scores)

    def test_higher_score_for_matching_content(self):
        chunks = [
            ({"content": "quantum physics entanglement theory"}, 0.9),
            ({"content": "quantum mechanics principles"}, 0.85),
            ({"content": "cooking recipes pasta"}, 0.5),
        ]
        scores = _bm25_score("quantum physics", chunks)
        # First chunk has both "quantum" and "physics" - should be highest
        assert scores[0] > 0
        # Non-matching chunk should have lower score
        assert scores[0] > scores[2]

    def test_empty_chunks_returns_empty(self):
        scores = _bm25_score("test", [])
        assert scores == []

    def test_case_insensitive(self):
        chunks = [
            ({"content": "Python Programming"}, 0.8),
            ({"content": "javascript"}, 0.6),
        ]
        scores_lower = _bm25_score("python", chunks)
        scores_upper = _bm25_score("PYTHON", chunks)
        assert scores_lower[0] == pytest.approx(scores_upper[0])


class TestReciprocalRankFusion:
    def test_combines_two_rankings(self):
        ranking1 = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
        ranking2 = [("b", 0.95), ("a", 0.85), ("c", 0.6)]

        result = _reciprocal_rank_fusion(ranking1, ranking2)
        assert len(result) == 3
        # Both "a" and "b" should be close due to RRF - just check they're on top
        top_items = [r[0] for r in result[:2]]
        assert "a" in top_items and "b" in top_items
        assert all(0 <= score <= 1 for _, score in result)

    def test_single_ranking(self):
        ranking = [("x", 0.9), ("y", 0.5)]
        result = _reciprocal_rank_fusion(ranking)
        assert len(result) == 2

    def test_empty_ranking(self):
        result = _reciprocal_rank_fusion([])
        assert result == []

    def test_preserves_item_identity(self):
        item_a = {"id": "a"}
        item_b = {"id": "b"}
        ranking = [(item_a, 0.9), (item_b, 0.8)]
        result = _reciprocal_rank_fusion(ranking)
        assert result[0][0]["id"] == "a"
        assert result[1][0]["id"] == "b"

    def test_k_parameter_affects_scores(self):
        ranking = [("a", 0.9), ("b", 0.8)]
        result60 = _reciprocal_rank_fusion(ranking, k=60)
        result10 = _reciprocal_rank_fusion(ranking, k=10)
        # Different k values should produce different scores
        assert result60[0][1] != result10[0][1]
