# Chunking Service

**File:** `app/services/chunking.py`

## Responsibilities
- Split documents into chunks (sliding window)
- Default: 2,048 characters per chunk (~512 tokens), 256-character overlap (~64 tokens)
- Handle edge cases (tables, formulas, multi-column PDFs)

## Key Functions
```
sliding_window_chunks(
    text: str,
    chunk_size: int = 2048,
    overlap: int = 256
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
