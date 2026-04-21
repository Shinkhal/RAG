# Chunking Service

**File:** `app/services/chunking.py`

## Responsibilities
- Split documents into chunks (sliding window)
- Default: 512 tokens per chunk, 64-token overlap
- Handle edge cases (tables, formulas, multi-column PDFs)

## Key Functions
```
sliding_window_chunks(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64
) -> list[str]

batched(items: list[str], size: int) -> Iterator[list[str]]
```

## Strategy
- Sliding window with 10-15% overlap
- Batch embed 32-128 chunks per Gemini call
- Idempotent: dedupe by `sha256(doc_id + chunk_idx)`

## Notes
- Used in ingestion pipeline
- Configurable per request (see `ChunkingConfig` schema)
