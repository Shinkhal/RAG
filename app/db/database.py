from __future__ import annotations

import os
import asyncio
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


async def init_db() -> None:
    """Initialize database connection, extensions, and tables."""
    logger.info("Starting database initialization...")
    try:
        await asyncio.to_thread(check_connection)
        logger.info("Database connection verified.")

        # Import models here to ensure they are registered with Base.metadata
        from . import models  # noqa: F401

        logger.info("Models imported, starting sync connection...")

        def _sync_setup() -> None:
            with sync_engine.begin() as conn:
                logger.info("Sync connection established, creating extensions...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

                # Run manual migrations if they exist
                if MIGRATIONS_DIR.exists():
                    logger.info(f"Running migrations from {MIGRATIONS_DIR}...")
                    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
                    for sql_file in migration_files:
                        logger.info(f"Executing migration: {sql_file.name}")
                        sql_content = sql_file.read_text(encoding="utf-8")
                        statements = _split_sql_statements(sql_content)
                        for stmt in statements:
                            conn.exec_driver_sql(stmt)

            logger.info("Extensions and migrations verified, creating tables...")
            # Create all tables defined in models (that might not be in migrations)
            Base.metadata.create_all(sync_engine)

        await asyncio.to_thread(_sync_setup)

        logger.info("✅ Database initialized (extensions, migrations and tables verified)")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        if settings.is_production:
            raise


async def get_session() -> AsyncSession:
    """Dependency for async database sessions."""
    async with async_session() as session:
        yield session
