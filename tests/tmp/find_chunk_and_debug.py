import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_session
from app.db.models import Document, Chunk
from sqlalchemy import select

TARGET_SNIPPET = "The digestive system breaks down food into nutrients that the body can absorb and use for energy"

async def main():
    async for session in get_session():
        stmt = select(Chunk)
        result = await session.execute(stmt)
        chunks = list(result.scalars().all())
        found = []
        for c in chunks:
            if TARGET_SNIPPET.lower() in (c.content or "").lower():
                found.append(c)
        print(f"Found {len(found)} matching chunks")
        for c in found[:10]:
            print(c.document_id, c.user_id, c.session_id, c.chunk_idx)
        return

if __name__ == '__main__':
    asyncio.run(main())
