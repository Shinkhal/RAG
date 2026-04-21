# Ingestion Service

**File:** `app/services/ingestion.py`

## Responsibilities
- Orchestrate async ingestion jobs
- Chunk documents
- Embed chunks (batch for speed)
- Store chunks in Supabase pgvector
- Track job status (queued → processing → processed/failed)

## Key Functions
```
submit_ingest_job(request: IngestRequest) -> str
    Returns: job_id

process_ingest_job(job_id: str, request: IngestRequest) -> None
    Async task: chunks, embeds, stores, updates status
```

## Job States
1. `queued` – waiting to process
2. `processing` – actively chunking/embedding
3. `processed` – success, chunks_created set
4. `failed` – error set

## Metadata Per Chunk
```
{
  "chunk_id": "sha256(doc_id + idx)",
  "document_id": "...",
  "user_id": "...",
  "page": 12,
  "chunk_idx": 5,
  "total_chunks": 120,
  "text": "...",
  "embedding": [...],     # 768 dims
  "created_at": "iso8601",
  "embed_version": "gemini-text-embedding-004"
}
```

## Integration
- Triggered by `POST /rag/ingest` endpoint
- Uses worker queue (BullMQ / RQ abstraction)
- Status polled via `GET /rag/ingest/status/{job_id}`
