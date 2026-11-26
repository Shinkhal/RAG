from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.repositories.supabase_repo import SupabaseRepo


@pytest.mark.asyncio
async def test_lexical_search_scopes_to_session_and_optional_documents() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        document_id="doc-1",
        session_id="session-1",
        user_id="student-1",
        chunk_idx=4,
        content="Biology study notes",
        embedding=None,
        metadata={},
        created_at=datetime.now(timezone.utc),
        score=0.75,
    )
    fake_result = SimpleNamespace(fetchall=lambda: [row])
    fake_session = SimpleNamespace(execute=AsyncMock(return_value=fake_result))
    repo = SupabaseRepo(fake_session)

    results = await repo.lexical_search(
        query="biology | study",
        user_id="student-1",
        session_id="session-1",
        top_k=5,
        document_ids=["doc-1"],
    )

    statement = str(fake_session.execute.await_args.args[0])
    params = fake_session.execute.await_args.args[1]
    assert "c.user_id = :user_id" in statement
    assert "c.session_id = :session_id" in statement
    assert "c.document_id IN (:doc_id_0)" in statement
    assert params["tsquery"] == "biology | study"
    assert params["user_id"] == "student-1"
    assert params["session_id"] == "session-1"
    assert len(results) == 1
    assert results[0][0].document_id == "doc-1"
    assert results[0][1] == 0.75


@pytest.mark.asyncio
async def test_lexical_search_returns_empty_for_no_terms() -> None:
    fake_session = SimpleNamespace(execute=AsyncMock())
    repo = SupabaseRepo(fake_session)

    results = await repo.lexical_search(
        query=" | ! ?",
        user_id="student-1",
        session_id="session-1",
    )

    assert results == []
    fake_session.execute.assert_not_awaited()
