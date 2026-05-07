import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.repositories.supabase_repo import SupabaseRepo
from app.services.retrieval import retrieve_chunks
from app.db import get_session

# This script requires a running DB configured via env vars used by the repo.
# It attempts to run retrieve_chunks for a sample query.

async def main():
    # Minimal fake session - uses real DB from env
    session = await get_session().__anext__()
    repo = SupabaseRepo(session)
    query = "which system breaks down food into nutrients that the body can absorb and use for energy"
    # Use IDs matching the chunks found in DB
    res = await retrieve_chunks(query=query, user_id="test-user-001", session_id="225997c0-705c-4731-b7c1-21d6f97871b2", repo=repo)
    print("low_confidence:", res.low_confidence)
    print("chunks:")
    for c, s in res.chunks:
        print(s, c.get("doc_id"), c.get("chunk_idx"), c.get("metadata"))
    print("debug:", res.debug)

if __name__ == "__main__":
    asyncio.run(main())
