import asyncio
import re
from dataclasses import dataclass
from functools import lru_cache
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
    "about",
    "into",
    "from",
    "with",
    "this",
    "that",
    "these",
    "those",
    "have",
    "will",
    "would",
    "could",
    "should",
    "your",
    "their",
    "there",
    # Short function words (previously excluded by ≥4 char filter)
    "is",
    "of",
    "to",
    "in",
    "on",
    "at",
    "by",
    "an",
    "or",
    "no",
    "if",
    "do",
    "so",
    "be",
    "as",
    "it",
    "am",
    "us",
    "we",
    "he",
    "me",
    "my",
    "up",
    "are",
    "was",
    "the",
    "and",
    "but",
    "not",
    "for",
    "has",
    "had",
    "can",
    "did",
    "may",
    "its",
    "our",
    "his",
    "her",
    "all",
    "any",
    "get",
    "got",
    "does",
    "been",
    "also",
    "than",
    "then",
    "them",
    "each",
    "over",
    "some",
    "very",
    "just",
    "more",
    "most",
    "such",
    "much",
    "only",
}


@lru_cache(maxsize=1)
def _get_cross_encoder():
    from sentence_transformers import CrossEncoder

    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


def _tokenize_words(text: str, minimum_length: int = 1) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= minimum_length]


def _signal_words(text: str) -> set[str]:
    return {
        word
        for word in _tokenize_words(text, minimum_length=1)
        if (len(word) >= 2) or word.isdigit()
    }


def _keyword_boost(text: str, query: str) -> float:
    query_words = _parse_query_words(query)
    text_words = _signal_words(text)
    matches = sum(1 for w in query_words if w in text_words)
    return matches * 0.05


def _topic_overlap(text: str, query_words: set[str]) -> float:
    text_words = _signal_words(text)
    if not query_words:
        return 0.0
    overlap = text_words & query_words
    return len(overlap) / len(query_words)


def _has_strong_lexical_signal(text: str, query_words: set[str], minimum_matches: int = 3) -> bool:
    text_words = _signal_words(text)
    return len(text_words & query_words) >= minimum_matches


def _deduplicate_chunks(
    chunks: list[tuple[dict[str, Any], float]],
) -> list[tuple[dict[str, Any], float]]:
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[dict[str, Any], float]] = []

    for item in chunks:
        chunk = item[0]
        content = chunk["content"].strip()
        key = (str(chunk.get("doc_id", "")), content)
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def _parse_query_words(query: str) -> set[str]:
    """Memoizable query word parsing."""
    return {
        word
        for word in _tokenize_words(query, minimum_length=1)
        if (len(word) >= 2) or word.isdigit()
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

    tokenized_chunks = [_tokenize_words(c["content"]) for c, _ in chunks]

    # Create BM25 model
    bm25 = BM25Okapi(tokenized_chunks)

    # Tokenize query
    query_tokens = [word for word in _tokenize_words(query) if word not in QUERY_STOPWORDS]

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
    Uses (doc_id, chunk_idx) as stable identity key for dict items.
    """
    scores: dict[Any, float] = {}
    items: dict[Any, Any] = {}

    for ranking in rankings:
        for rank, (item, _) in enumerate(ranking, 1):
            # Use content-based key for chunk dicts, identity for others
            if isinstance(item, dict) and "doc_id" in item and "chunk_idx" in item:
                item_key: Any = (item["doc_id"], item["chunk_idx"])
            elif isinstance(item, dict):
                item_key = id(item)
            else:
                item_key = item
            if item_key not in scores:
                scores[item_key] = 0.0
                items[item_key] = item
            scores[item_key] += 1 / (k + rank)

    # Convert back to sorted list
    results = [(items[item_key], score) for item_key, score in scores.items()]
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

    # Keep the student's original wording for lexical search, reranking, and
    # confidence. Rewriting is only used to make the embedding query broader.
    embedding_query = query
    if settings.enable_query_rewriting:
        try:
            embedding_query = await rewrite_query(query)
        except Exception:
            pass  # Fallback to original query

    query_embedding = await gemini_client.embed_query(embedding_query)
    query_words = _parse_query_words(query)

    vector_results = await repo.similarity_search(
        embedding=query_embedding,
        user_id=user_id,
        session_id=session_id,
        top_k=top_k * 4,
        min_score=min_score,
        document_ids=document_ids,
    )
    lexical_results = (
        await repo.lexical_search(
            query=" ".join(sorted(query_words)),
            user_id=user_id,
            session_id=session_id,
            top_k=top_k * 4,
            document_ids=document_ids,
        )
        if use_bm25 and query_words
        else []
    )

    if not vector_results and not lexical_results:
        return RetrievalResult(chunks=[], low_confidence=True)

    # Merge vector and full-session lexical candidates by stable chunk identity.
    candidate_items: dict[tuple[str, int], dict[str, Any]] = {}
    vector_ranking: list[tuple[dict[str, Any], float]] = []
    lexical_ranking: list[tuple[dict[str, Any], float]] = []
    debug_records: list[dict[str, Any]] = []

    for chunk, raw_score in vector_results:
        clean_content = sanitize_context([{"content": chunk.content}])[0]["content"]
        boost = _keyword_boost(clean_content, query)
        final_score = min(raw_score + boost, 1.0)
        topic_score = _topic_overlap(clean_content, query_words)
        combined_score = final_score * (1 + topic_score)
        key = (chunk.document_id, chunk.chunk_idx)
        item = candidate_items.setdefault(
            key,
            {
                "content": clean_content,
                "doc_id": chunk.document_id,
                "chunk_idx": chunk.chunk_idx,
                "metadata": chunk.metadata_,
                "vector_score": 0.0,
                "lexical_score": 0.0,
            },
        )
        item["vector_score"] = float(raw_score)
        vector_ranking.append((item, combined_score))
        debug_records.append({
            "doc_id": chunk.document_id,
            "chunk_idx": chunk.chunk_idx,
            "raw_score": raw_score,
            "keyword_boost": boost,
            "final_score": final_score,
            "topic_score": topic_score,
            "combined_score": combined_score,
            "filename": chunk.metadata_.get("filename") if isinstance(chunk.metadata_, dict) else None,
        })

    for chunk, lexical_score in lexical_results:
        key = (chunk.document_id, chunk.chunk_idx)
        item = candidate_items.setdefault(
            key,
            {
                "content": sanitize_context([{"content": chunk.content}])[0]["content"],
                "doc_id": chunk.document_id,
                "chunk_idx": chunk.chunk_idx,
                "metadata": chunk.metadata_,
                "vector_score": 0.0,
                "lexical_score": 0.0,
            },
        )
        item["lexical_score"] = float(lexical_score)
        lexical_ranking.append((item, float(lexical_score)))

    scored: list[tuple[dict[str, Any], float]]
    if use_bm25:
        candidates = list(candidate_items.values())
        bm25_scores = _bm25_score(query, [(item, 0.0) for item in candidates])
        bm25_ranking = sorted(
            [(candidates[index], score) for index, score in enumerate(bm25_scores)],
            key=lambda item: item[1],
            reverse=True,
        )
        if vector_ranking and bm25_ranking and max(bm25_scores) > min(bm25_scores):
            scored = _reciprocal_rank_fusion(
                sorted(vector_ranking, key=lambda item: item[1], reverse=True),
                bm25_ranking,
            )
        elif vector_ranking and lexical_ranking:
            scored = _reciprocal_rank_fusion(
                sorted(vector_ranking, key=lambda item: item[1], reverse=True),
                sorted(lexical_ranking, key=lambda item: item[1], reverse=True),
            )
        else:
            scored = vector_ranking or bm25_ranking or lexical_ranking
    else:
        scored = vector_ranking

    # Apply cross-encoder reranking if enabled
    if use_reranking and len(scored) > 1:
        try:
            model = await asyncio.to_thread(_get_cross_encoder)

            # Prepare pairs for reranking
            pairs = [(query, c["content"]) for c, _ in scored[:top_k * 2]]

            # Get reranking scores
            rerank_scores = await asyncio.to_thread(model.predict, pairs)

            # Combine with RRF scores
            reranked = list(zip(scored[:top_k * 2], rerank_scores))
            reranked.sort(key=lambda pair: float(pair[1]), reverse=True)
            scored = [item_score for item_score, _ in reranked] + scored[top_k * 2 :]
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
                    chunk_data["chunk_idx"],
                    chunk_data["doc_id"],
                    repo,
                    user_id,
                    context_window=settings.parent_context_window
                )
                enriched.append(({**chunk_data, "parent_context": parent_text}, score))
            except Exception:
                enriched.append((chunk_data, score))
        top = enriched

    top_content = top[0][0]["content"] if top else ""
    top_vector_score = top[0][0].get("vector_score", 0.0) if top else 0.0
    top_topic_overlap = _topic_overlap(top_content, query_words)
    top_lexical_score = top[0][0].get("lexical_score", 0.0) if top else 0.0
    strong_lexical_signal = (
        top_lexical_score > 0
        or _has_strong_lexical_signal(top_content, query_words, min_keyword_matches)
    )
    # Trust high vector scores even when topic overlap is low —
    # prevents false "not enough info" when the embedding match is strong
    low_confidence = (
        bool(top)
        and (not query_words or top_topic_overlap < topic_threshold)
        and not strong_lexical_signal
        and top_vector_score < 0.75
    )

    debug_info = debug_records if low_confidence else None

    return RetrievalResult(chunks=top, low_confidence=low_confidence, debug=debug_info)
