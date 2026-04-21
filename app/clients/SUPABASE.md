# Supabase Vector Client

**File:** `app/clients/supabase.py`

## Responsibilities
- Upsert chunks to `chunks` table
- Similarity search via pgvector HNSW index
- Apply user_id + document_id filters
- Support date range filters

## Key Methods
```
upsert_chunks(chunks: list[ChunkRecord]) -> None
similarity_search(
    embedding: list[float],
    user_id: str,
    top_k: int = 20,
    min_score: float = 0.7,
    document_ids: list[str] = None,
    date_range: DateRange = None
) -> list[ChunkRecord]
```

## Schema Reference
- Table: `chunks` (id, document_id, user_id, chunk_idx, content, embedding, metadata, created_at)
- Index: HNSW on `embedding` column (cosine_ops)
- Index: on (user_id, document_id)

