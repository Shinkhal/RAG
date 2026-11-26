from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.supabase_repo import ChunkRecord, SupabaseRepo


class _NestedTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: Any) -> None:
        return None


class _Session:
    def __init__(self) -> None:
        self.statements = []

    def begin_nested(self) -> _NestedTransaction:
        return _NestedTransaction()

    async def execute(self, statement, *_args: Any, **_kwargs: Any) -> _Result:
        self.statements.append(statement)
        return _Result()

    async def commit(self) -> None:
        return None


class _Result:
    def fetchall(self) -> list[Any]:
        return []


@pytest.mark.asyncio
async def test_chunk_upsert_uses_stable_identity_and_removes_old_tail() -> None:
    session = _Session()
    repo = SupabaseRepo(session)  # type: ignore[arg-type]

    saved = await repo.upsert_chunks([
        ChunkRecord(
            document_id="doc-1",
            session_id="session-1",
            user_id="user-1",
            chunk_idx=0,
            content="updated chunk",
            embedding=[0.1, 0.2],
        )
    ])

    sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert saved == 1
    assert "ON CONFLICT (document_id, chunk_idx) DO UPDATE" in sql
    assert len(session.statements) == 2


@pytest.mark.asyncio
async def test_vector_search_filters_embedding_versions_without_score_pruning() -> None:
    session = _Session()
    repo = SupabaseRepo(session)  # type: ignore[arg-type]

    await repo.similarity_search(
        embedding=[0.1, 0.2],
        user_id="user-1",
        session_id="session-1",
        min_score=0.99,
    )

    query = str(session.statements[1])
    assert "d.embed_version = :embedding_model" in query
    assert "score)) >= :min_score" not in query
