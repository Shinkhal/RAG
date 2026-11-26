"""Run database migrations as a deployment step: ``python -m app.db.migrate``."""

import asyncio

from app.db.database import migrate_db

if __name__ == "__main__":
    asyncio.run(migrate_db())
