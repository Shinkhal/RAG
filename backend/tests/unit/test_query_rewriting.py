import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.retrieval import rewrite_query


class TestRewriteQuery:
    async def test_falls_back_on_error(self):
        """Test fallback to original query on LLM error."""
        with patch("app.services.retrieval.gemini_client") as mock_client:
            mock_client.generate = AsyncMock(
                side_effect=Exception("API Error")
            )

            result = await rewrite_query("original query")
            assert result == "original query"

    async def test_falls_back_on_empty_response(self):
        """Test fallback when LLM returns empty response."""
        with patch("app.services.retrieval.gemini_client") as mock_client:
            mock_client.generate = AsyncMock(return_value="")

            result = await rewrite_query("original query")
            assert result == "original query"

    async def test_returns_rewritten_query(self):
        """Test that LLM rewrites the query."""
        with patch("app.services.retrieval.gemini_client") as mock_client:
            mock_client.generate = AsyncMock(return_value="rewritten query")

            result = await rewrite_query("original query")
            assert result == "rewritten query"
