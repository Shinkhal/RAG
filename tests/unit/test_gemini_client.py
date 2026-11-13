import math
from types import SimpleNamespace

import pytest

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


@pytest.mark.asyncio
async def test_embed_documents_retries_one_by_one_on_short_batch_response() -> None:
    client = GeminiClient.__new__(GeminiClient)
    client._embedding_model = "gemini-embedding-2"
    client._embedding_output_dimensionality = 3072

    calls: list[object] = []

    async def fake_embed_content(*, model, contents, config):
        calls.append(contents)
        if isinstance(contents, list):
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0, 2.0])])
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0])])

    client.client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(embed_content=fake_embed_content))
    )

    result = await client.embed_documents(["a", "b", "c"], batch_size=32)

    assert len(result) == 3
    assert calls[0] == ["a", "b", "c"]
    assert calls[1:] == ["a", "b", "c"]
