import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.retrieval import get_parent_context


class TestGetParentContext:
    async def test_fetchs_surrounding_chunks(self):
        """Test that parent context fetches chunks around target."""
        mock_repo = AsyncMock()

        # Mock chunks: idx 0, 1, 2, 3, 4
        mock_chunks = [
            MagicMock(chunk_idx=i, content=f"Chunk {i} content")
            for i in range(5)
        ]
        mock_repo.get_chunks_by_idx_range.return_value = mock_chunks

        result = await get_parent_context(
            chunk_idx=2,
            document_id="doc1",
            repo=mock_repo,
            user_id="user1",
            context_window=1
        )

        # Should include chunks 1, 2, 3
        assert "Chunk 1 content" in result
        assert "Chunk 2 content" in result
        assert "Chunk 3 content" in result

    async def test_handles_start_boundary(self):
        """Test that it handles chunk at start of document."""
        mock_repo = AsyncMock()
        mock_chunks = [
            MagicMock(chunk_idx=0, content="First chunk")
        ]
        mock_repo.get_chunks_by_idx_range.return_value = mock_chunks

        result = await get_parent_context(
            chunk_idx=0,
            document_id="doc1",
            repo=mock_repo,
            user_id="user1",
            context_window=2
        )

        assert "First chunk" in result

    async def test_handles_end_boundary(self):
        """Test that it handles chunk at end of document."""
        mock_repo = AsyncMock()
        mock_chunks = [
            MagicMock(chunk_idx=4, content="Last chunk")
        ]
        mock_repo.get_chunks_by_idx_range.return_value = mock_chunks

        result = await get_parent_context(
            chunk_idx=4,
            document_id="doc1",
            repo=mock_repo,
            user_id="user1",
            context_window=2
        )

        assert "Last chunk" in result

    async def test_returns_concatenated_text(self):
        """Test that chunks are sorted and concatenated."""
        mock_repo = AsyncMock()

        # Return out-of-order chunks
        mock_chunks = [
            MagicMock(chunk_idx=2, content="Second"),
            MagicMock(chunk_idx=1, content="First"),
        ]
        mock_repo.get_chunks_by_idx_range.return_value = mock_chunks

        result = await get_parent_context(
            chunk_idx=1,
            document_id="doc1",
            repo=mock_repo,
            user_id="user1",
            context_window=1
        )

        # Should be sorted: First, Second
        assert result.index("First") < result.index("Second")
