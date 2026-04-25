import math

from app.clients.gemini import GeminiClient


def test_l2_normalize_returns_unit_vector() -> None:
    normalized = GeminiClient._l2_normalize([3.0, 4.0])

    assert math.isclose(normalized[0], 0.6, rel_tol=1e-9)
    assert math.isclose(normalized[1], 0.8, rel_tol=1e-9)
    assert math.isclose(math.sqrt(sum(v * v for v in normalized)), 1.0, rel_tol=1e-9)


def test_l2_normalize_handles_zero_vector() -> None:
    zero_vec = [0.0, 0.0, 0.0]

    assert GeminiClient._l2_normalize(zero_vec) == zero_vec


def test_normalize_if_needed_skips_for_embedding_001() -> None:
    """gemini-embedding-001 is NOT gemini-embedding-2, so no normalization."""
    client = GeminiClient.__new__(GeminiClient)
    client._embedding_model = "gemini-embedding-001"
    client._embedding_output_dimensionality = 768

    values = [3.0, 4.0]
    assert client._normalize_if_needed(values) == values


def test_normalize_if_needed_normalizes_for_embedding_2_non_3072() -> None:
    """gemini-embedding-2 with non-3072 dims should L2-normalize."""
    client = GeminiClient.__new__(GeminiClient)
    client._embedding_model = "gemini-embedding-2"
    client._embedding_output_dimensionality = 768

    normalized = client._normalize_if_needed([3.0, 4.0])
    assert math.isclose(normalized[0], 0.6, rel_tol=1e-9)
    assert math.isclose(normalized[1], 0.8, rel_tol=1e-9)


def test_normalize_if_needed_skips_for_3072() -> None:
    client = GeminiClient.__new__(GeminiClient)
    client._embedding_model = "gemini-embedding-2"
    client._embedding_output_dimensionality = 3072

    values = [3.0, 4.0]
    assert client._normalize_if_needed(values) == values
