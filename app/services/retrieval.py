from dataclasses import dataclass
from typing import Any

from app.clients.gemini import gemini_client
from app.repositories.supabase_repo import SupabaseRepo
from app.services.security import sanitize_context


@dataclass
class RetrievalResult:
    chunks: list[tuple[dict[str, Any], float]]
    low_confidence: bool  # topic overlap below threshold


def _keyword_boost(text: str, query: str) -> float:
    query_words = [w.lower() for w in query.split() if len(w) > 2]
    text_lower = text.lower()
    matches = sum(1 for w in query_words if w in text_lower)
    return matches * 0.05


def _topic_overlap(text: str, query_words: set[str]) -> float:
    text_words = set(w.lower() for w in text.split() if len(w) > 3)
    if not query_words:
        return 0.0
    overlap = text_words & query_words
    return len(overlap) / len(query_words)


def _deduplicate_chunks(
    chunks: list[tuple[dict[str, Any], float]],
) -> list[tuple[dict[str, Any], float]]:
    seen: list[str] = []
    unique: list[tuple[dict[str, Any], float]] = []

    for item in chunks:
        content = item[0]["content"]
        key = content[:400]
        if key not in seen:
            seen.append(key)
            unique.append(item)

    return unique


def _parse_query_words(query: str) -> set[str]:
    """Memoizable query word parsing."""
    return {w.lower() for w in query.split() if len(w) > 2}


async def retrieve_chunks(
    query: str,
    user_id: str,
    session_id: str,
    repo: SupabaseRepo,
    top_k: int = 5,
    min_score: float = 0.5,
    document_ids: list[str] | None = None,
    topic_threshold: float = 0.15,
) -> RetrievalResult:
    query_embedding = await gemini_client.embed_query(query)
    query_words = _parse_query_words(query)

    results = await repo.similarity_search(
        embedding=query_embedding,
        user_id=user_id,
        session_id=session_id,
        top_k=top_k * 4,
        min_score=min_score,
        document_ids=document_ids,
    )

    scored: list[tuple[dict[str, Any], float]] = []
    for chunk, raw_score in results:
        clean_content = sanitize_context([{"content": chunk.content}])[0]["content"]
        boost = _keyword_boost(clean_content, query)
        final_score = min(raw_score + boost, 1.0)

        topic_score = _topic_overlap(clean_content, query_words)
        combined_score = final_score * (1 + topic_score)

        scored.append(
            (
                {
                    "content": clean_content,
                    "doc_id": chunk.document_id,
                    "chunk_idx": chunk.chunk_idx,
                    "metadata": chunk.metadata_,
                },
                min(combined_score, 1.0),
            )
        )

    sorted_chunks = sorted(scored, key=lambda x: x[1], reverse=True)
    unique_chunks = _deduplicate_chunks(sorted_chunks)
    top = unique_chunks[:top_k]

    low_confidence = top and _topic_overlap(top[0][0]["content"], query_words) < topic_threshold

    return RetrievalResult(chunks=top, low_confidence=low_confidence)
