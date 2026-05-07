import re
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Okapi

from app.clients.gemini import gemini_client
from app.repositories.supabase_repo import SupabaseRepo
from app.services.security import sanitize_context


@dataclass
class RetrievalResult:
    chunks: list[tuple[dict[str, Any], float]]
    low_confidence: bool  # topic overlap below threshold
    debug: list[dict[str, Any]] | None = None


QUERY_STOPWORDS = {
    "what",
    "which",
    "when",
    "where",
    "who",
    "whom",
    "whose",
    "why",
    "how",
    "tell",
    "explain",
    "define",
    "describe",
}


def _tokenize_words(text: str, minimum_length: int = 1) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= minimum_length]


def _keyword_boost(text: str, query: str) -> float:
    query_words = _parse_query_words(query)
    text_words = set(_tokenize_words(text, minimum_length=4))
    matches = sum(1 for w in query_words if w in text_words)
    return matches * 0.05


def _topic_overlap(text: str, query_words: set[str]) -> float:
    text_words = set(_tokenize_words(text, minimum_length=4))
    if not query_words:
        return 0.0
    overlap = text_words & query_words
    return len(overlap) / len(query_words)


def _has_strong_lexical_signal(text: str, query_words: set[str], minimum_matches: int = 3) -> bool:
    text_words = set(_tokenize_words(text, minimum_length=4))
    return len(text_words & query_words) >= minimum_matches


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
    return {
        word
        for word in _tokenize_words(query, minimum_length=4)
        if word not in QUERY_STOPWORDS
    }


async def rewrite_query(query: str, subscription_tier: str = "free") -> str:
    """
    Rewrite query to improve retrieval.
    Uses LLM to expand abbreviations, add synonyms, or break complex queries.
    Falls back to original query on error.
    """
    try:
        rewrite_prompt = f"""Rewrite this search query to improve document retrieval.
Options: add synonyms, expand abbreviations, break into sub-questions.
Keep it concise and focused.

Original: {query}
Rewritten:"""

        # Use the module-level Gemini client (patchable in tests)
        result = await gemini_client.generate(
            prompt=rewrite_prompt,
            temperature=0.3,
            max_tokens=100,
        )

        if result and len(result.strip()) > 0:
            return result.strip()
    except Exception:
        pass

    return query  # Fallback to original


def _bm25_score(query: str, chunks: list[tuple[dict[str, Any], float]]) -> list[float]:
    """Calculate BM25 scores for query-chunk pairs."""
    if not chunks:
        return []

    # Tokenize chunk texts - c is already the dict from tuple unpacking
    tokenized_chunks = [c["content"].lower().split() for c, _ in chunks]

    # Create BM25 model
    bm25 = BM25Okapi(tokenized_chunks)

    # Tokenize query
    query_tokens = query.lower().split()

    # Get scores
    scores = bm25.get_scores(query_tokens)
    return list(scores)


def _reciprocal_rank_fusion(
    *rankings: list[tuple[Any, float]],
    k: int = 60
) -> list[tuple[Any, float]]:
    """
    Combine multiple rankings using Reciprocal Rank Fusion.
    Formula: RRF(d) = sum(1 / (k + rank_i(d)))
    """
    scores = {}
    items = {}

    for ranking in rankings:
        for rank, (item, _) in enumerate(ranking, 1):
            item_id = id(item)
            if item_id not in scores:
                scores[item_id] = 0.0
                items[item_id] = item
            scores[item_id] += 1 / (k + rank)

    # Convert back to sorted list
    results = [(items[item_id], score) for item_id, score in scores.items()]
    return sorted(results, key=lambda x: x[1], reverse=True)


async def get_parent_context(
    chunk_idx: int,
    document_id: str,
    repo: SupabaseRepo,
    user_id: str,
    context_window: int = 2,
) -> str:
    """
    Fetch parent document context around a specific chunk.
    Returns concatenated text of surrounding chunks for richer context.
    """
    start_idx = max(0, chunk_idx - context_window)
    end_idx = chunk_idx + context_window

    chunks = await repo.get_chunks_by_idx_range(
        document_id, user_id, start_idx, end_idx
    )

    # Sort by chunk_idx and concatenate
    sorted_chunks = sorted(chunks, key=lambda c: c.chunk_idx)
    return "\n\n".join(c.content for c in sorted_chunks)


async def retrieve_chunks(
    query: str,
    user_id: str,
    session_id: str,
    repo: SupabaseRepo,
    top_k: int = 5,
    min_score: float = 0.5,
    document_ids: list[str] | None = None,
    topic_threshold: float | None = None,
    use_bm25: bool | None = None,
    use_reranking: bool | None = None,
    min_keyword_matches: int | None = None,
) -> RetrievalResult:
    from app.config.env_config import get_settings

    settings = get_settings()

    if use_bm25 is None:
        use_bm25 = settings.enable_bm25
    if use_reranking is None:
        use_reranking = settings.enable_reranking
    if topic_threshold is None:
        topic_threshold = settings.topic_threshold
    if min_keyword_matches is None:
        min_keyword_matches = settings.min_keyword_matches

    # Query rewriting for better retrieval
    if settings.enable_query_rewriting:
        try:
            query = await rewrite_query(query)
        except Exception:
            pass  # Fallback to original query

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

    if not results:
        return RetrievalResult(chunks=[], low_confidence=True)

    # Build initial scored list with vector + keyword + topic
    scored: list[tuple[dict[str, Any], float]] = []
    debug_records: list[dict[str, Any]] = []
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
        debug_records.append({
            "doc_id": chunk.document_id,
            "chunk_idx": chunk.chunk_idx,
            "raw_score": raw_score,
            "keyword_boost": boost,
            "final_score": final_score,
            "topic_score": topic_score,
            "combined_score": min(combined_score, 1.0),
            "filename": chunk.metadata_.get("filename") if isinstance(chunk.metadata_, dict) else None,
        })

    # Apply BM25 if enabled
    if use_bm25 and len(scored) > 1:
        bm25_scores = _bm25_score(query, scored)

        # Normalize BM25 scores to 0-1 range
        if bm25_scores:
            max_bm25 = max(bm25_scores)
            min_bm25 = min(bm25_scores)
            if max_bm25 > min_bm25:
                normalized_bm25 = [
                    (s - min_bm25) / (max_bm25 - min_bm25)
                    for s in bm25_scores
                ]
            else:
                normalized_bm25 = [0.5] * len(bm25_scores)
        else:
            normalized_bm25 = []

        # Combine vector + BM25 using RRF
        vector_ranking = [(item, score) for item, score in scored]
        bm25_ranking = [
            (scored[i][0], normalized_bm25[i]) for i in range(len(scored))
        ]

        scored = _reciprocal_rank_fusion(vector_ranking, bm25_ranking)

    # Apply cross-encoder reranking if enabled
    if use_reranking and len(scored) > 1:
        try:
            from sentence_transformers import CrossEncoder

            # Load model (caches after first load)
            model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

            # Prepare pairs for reranking
            pairs = [(query, c[0]["content"]) for c, _ in scored[:top_k * 2]]

            # Get reranking scores
            rerank_scores = model.predict(pairs)

            # Combine with RRF scores
            reranked = []
            for i, (item, orig_score) in enumerate(scored[:top_k * 2]):
                rerank_score = rerank_scores[i] if i < len(rerank_scores) else 0.0
                combined = (orig_score * 0.3) + (float(rerank_score) * 0.7)
                reranked.append((item, combined))

            scored = reranked
        except Exception:
            pass  # Fallback to RRF scores

    sorted_chunks = sorted(scored, key=lambda x: x[1], reverse=True)
    unique_chunks = _deduplicate_chunks(sorted_chunks)
    top = unique_chunks[:top_k]

    # Enrich with parent context if enabled
    if settings.enable_parent_context:
        enriched = []
        for chunk_data, score in top:
            try:
                parent_text = await get_parent_context(
                    chunk_data[0]["chunk_idx"],
                    chunk_data[0]["doc_id"],
                    repo,
                    user_id,
                    context_window=settings.parent_context_window
                )
                enriched.append(({**chunk_data[0], "parent_context": parent_text}, score))
            except Exception:
                enriched.append((chunk_data[0], score))
        top = enriched

    top_content = top[0][0]["content"] if top else ""
    top_topic_overlap = _topic_overlap(top_content, query_words)
    strong_lexical_signal = _has_strong_lexical_signal(top_content, query_words, min_keyword_matches)
    low_confidence = bool(top) and top_topic_overlap < topic_threshold and not strong_lexical_signal

    debug_info = debug_records if low_confidence else None

    return RetrievalResult(chunks=top, low_confidence=low_confidence, debug=debug_info)
