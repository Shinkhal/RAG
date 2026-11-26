"""Compatibility shim for legacy imports.

The single source of truth for database setup now lives in `app.db.database`.
Keep this module around so older imports continue to work, but do not add
database-specific logic here.
"""

from app.db.database import Base, async_session, engine, get_session, init_db

__all__ = ["Base", "async_session", "engine", "get_session", "init_db"]
