from __future__ import annotations

from pathlib import Path

import pytest

from app.config.env_config import GetEnv
from app.db import database


def test_split_sql_statements_ignores_comments_and_blank_lines() -> None:
    sql_text = """
    -- comment
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY);
    """

    assert database._split_sql_statements(sql_text) == [  # noqa: SLF001
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY)",
    ]


@pytest.mark.asyncio
async def test_init_db_executes_migration_files(monkeypatch: pytest.MonkeyPatch) -> None:
    statements: list[str] = []

    class FakeConnection:
        def execute(self, statement):
            statements.append(str(statement))
            return FakeResult()

        def exec_driver_sql(self, statement: str) -> None:
            statements.append(statement)

    class FakeResult:
        def scalar(self) -> int:
            return 1

    class FakeBegin:
        def __enter__(self) -> FakeConnection:
            return FakeConnection()

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakeEngine:
        def connect(self) -> FakeBegin:
            return FakeBegin()

        def begin(self) -> FakeBegin:
            return FakeBegin()

    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "migrations"

    monkeypatch.setattr(database, "sync_engine", FakeEngine())
    monkeypatch.setattr(database, "MIGRATIONS_DIR", fixture_dir)

    await database.init_db()

    assert statements == [
        "SELECT 1",
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE EXTENSION IF NOT EXISTS pgcrypto",
        "CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY)",
        "CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (id)",
    ]


def test_database_url_prefers_database_url_over_direct_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://db-url")

    assert GetEnv.database.url() == "postgresql://db-url"
    assert GetEnv.database.source() == "DATABASE_URL"


def test_engine_uses_null_pool() -> None:
    from sqlalchemy.pool import NullPool

    assert isinstance(database.engine.pool, NullPool)


def test_engine_disables_prepared_statement_cache() -> None:
    assert database.engine.url.query.get("prepared_statement_cache_size") == "0"


def test_check_connection_executes_select_one(monkeypatch: pytest.MonkeyPatch) -> None:
    statements: list[str] = []

    class FakeResult:
        def scalar(self) -> int:
            return 1

    class FakeConnection:
        def execute(self, statement):
            statements.append(str(statement))
            return FakeResult()

    class FakeContext:
        def __enter__(self) -> FakeConnection:
            return FakeConnection()

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakeEngine:
        def connect(self) -> FakeContext:
            return FakeContext()

    monkeypatch.setattr(database, "sync_engine", FakeEngine())

    database.check_connection()

    assert statements == ["SELECT 1"]
