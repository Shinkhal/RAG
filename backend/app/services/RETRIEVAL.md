# Retrieval Service

**File:** `app/services/retrieval.py`

## Responsibilities
- Vector similarity search
- Optional reranking (FlashRank / cohere-rerank-lite)
- Cache awareness
- Fallback to full-text search if slow

## Key Functions
```
retrieve_chunks(
    query: str,
    user_id: str,
    top_k: int = 5,
    score_threshold: float = 0.7,
    document_ids: list[str] = None,
    use_rerank: bool = True
) -> list[tuple[ChunkRecord, float]]
```

## Flow
1. Embed query (RETRIEVAL_QUERY task)
2. Search Postgres pgvector (top-20)
3. Rerank to top-5 (if enabled)
4. Apply score threshold (0.7 default)
5. Return with scores

## Cache Integration
- Check Redis for cached results
- TTL: 1 hour default
- Key: `query_cache:{user_id}:{query_hash}`

## Fallback
- If pgvector slow (> 300ms), fallback to FTS on `content` column
