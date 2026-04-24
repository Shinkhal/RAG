from typing import Any

from app.repositories.supabase_repo import SupabaseRepo, ChunkRecord
from app.clients.gemini import gemini_client
from app.services.security import sanitize_context


async def retrieve_chunks(
    query: str,
    user_id: str,
    repo: SupabaseRepo,
    top_k: int = 5,
    min_score: float = 0.7,
    document_ids: list[str] | None = None,
) -> list[tuple[dict[str, Any], float]]:
    query_embedding = await gemini_client.embed_query(query)

    results = await repo.similarity_search(
        embedding=query_embedding,
        user_id=user_id,
        top_k=top_k * 4,
        min_score=min_score,
        document_ids=document_ids,
    )

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

    return sorted(sanitized, key=lambda x: x[1], reverse=True)[:top_k]
