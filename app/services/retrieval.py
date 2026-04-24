from typing import Any

from app.repositories.supabase_repo import SupabaseRepo, ChunkRecord
from app.clients.gemini import gemini_client
from app.services.security import sanitize_context


async def retrieve_chunks(
    query: str,
    user_id: str,
    session_id: str,
    repo: SupabaseRepo,
    top_k: int = 10,
    min_score: float = 0.6,
    document_ids: list[str] | None = None,
) -> list[tuple[dict[str, Any], float]]:
    query_embedding = await gemini_client.embed_query(query)

    results = await repo.similarity_search(
        embedding=query_embedding,
        user_id=user_id,
        session_id=session_id,
        top_k=top_k * 4,
        min_score=min_score,
        document_ids=document_ids,
    )

    print("RAW DB RESULTS:", len(results))

    sanitized = []
    for chunk, score in results:
        clean_content = sanitize_context([{"content": chunk.content}])[0]["content"]
        sanitized.append(
            (
                {
                    "content": clean_content,
                    "doc_id": chunk.document_id,
                    "chunk_idx": chunk.chunk_idx,
                    "metadata": chunk.metadata_,
                },
                score,
            )
        )

    sorted_sanitized = sorted(sanitized, key=lambda x: x[1], reverse=True)
    
    seen = set()
    unique_chunks = []
    
    for item in sorted_sanitized:
        chunk = item[0]
        content = chunk["content"]
        if content not in seen:
            seen.add(content)
            unique_chunks.append(item)

    final_results = unique_chunks[:top_k]
    print("\n==== RETRIEVED CHUNKS ====")
    for i, (chunk, _) in enumerate(final_results):
        print(f"\n{i}: {chunk['content'][:300]}")

    return final_results
