"""Run database migrations as a deployment step: ``python -m app.db.migrate``."""

import asyncio

from app.config.env_config import GetEnv
from app.db.database import migrate_db
from app.utils.logger import configure_logging

if __name__ == "__main__":
    configure_logging()
    if GetEnv.app.is_prod():
        GetEnv.validate()
    asyncio.run(migrate_db())
