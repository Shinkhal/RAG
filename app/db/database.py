from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from app.config.env_config import get_settings, optional
from app.utils.logger import logger

settings = get_settings()
DATABASE_URL = settings.database_url

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"

# Sync engine for initial setup and health checks (always NullPool)
sync_engine = create_engine(DATABASE_URL, poolclass=NullPool)

# Async engine for the main application logic
# Use NullPool for serverless/PgBouncer by default in test/dev environments
USE_NULL_POOL = os.getenv("DATABASE_NULL_POOL", "true").lower() == "true"

ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
if "prepared_statement_cache_size" not in ASYNC_DATABASE_URL:
    if "?" in ASYNC_DATABASE_URL:
        ASYNC_DATABASE_URL += "&prepared_statement_cache_size=0"
    else:
        ASYNC_DATABASE_URL += "?prepared_statement_cache_size=0"

if USE_NULL_POOL:
    engine = create_async_engine(ASYNC_DATABASE_URL, poolclass=NullPool)
else:
    pool_size = int(optional("DATABASE_POOL_SIZE", "5"))
    max_overflow = int(optional("DATABASE_MAX_OVERFLOW", "10"))
    pool_timeout = int(optional("DATABASE_POOL_TIMEOUT", "30"))
    pool_recycle = int(optional("DATABASE_POOL_RECYCLE", "1800"))

    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
    )

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def check_connection() -> None:
    """Synchronously check if the database is reachable."""
    with sync_engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL string into individual statements, ignoring comments and empty lines."""
    statements = []
    for line in sql.split(";"):
        clean_line = ""
        for subline in line.split("\n"):
            stripped = subline.strip()
            if stripped and not stripped.startswith("--"):
                clean_line += " " + stripped

        final_stmt = clean_line.strip()
        if final_stmt:
            statements.append(final_stmt)
    return statements


def _sync_schema_setup() -> None:
    from . import models  # noqa: F401

    with sync_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(filename TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        ))
        conn.execute(text("SELECT pg_advisory_xact_lock(741852963)"))
        if MIGRATIONS_DIR.exists():
            for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
                sql_content = sql_file.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql_content.encode("utf-8")).hexdigest()
                applied = conn.execute(
                    text("SELECT checksum FROM schema_migrations WHERE filename = :filename"),
                    {"filename": sql_file.name},
                ).scalar_one_or_none()
                if applied:
                    if applied != checksum:
                        raise RuntimeError(f"Applied migration was modified: {sql_file.name}")
                    continue
                logger.info("Applying migration: %s", sql_file.name)
                for statement in _split_sql_statements(sql_content):
                    conn.exec_driver_sql(statement)
                conn.execute(
                    text("INSERT INTO schema_migrations (filename, checksum) VALUES (:filename, :checksum)"),
                    {"filename": sql_file.name, "checksum": checksum},
                )
    Base.metadata.create_all(sync_engine)


async def migrate_db() -> None:
    """Apply pending versioned SQL migrations (run as a deployment step)."""
    await asyncio.to_thread(check_connection)
    await asyncio.to_thread(_sync_schema_setup)


async def init_db() -> None:
    """Check connectivity; migrations run automatically only outside production."""
    try:
        await asyncio.to_thread(check_connection)
        if not settings.is_production:
            await migrate_db()
        else:
            logger.info("Production database connected; schema is managed by deploy migrations.")
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
        if settings.is_production:
            raise


async def get_session() -> AsyncSession:
    """Dependency for async database sessions."""
    async with async_session() as session:
        yield session
