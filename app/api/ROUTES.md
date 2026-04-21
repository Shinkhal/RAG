# API Routes

## Ingestion Routes (`app/api/routes/ingest.py`)

**`POST /rag/ingest`**
- Request: `IngestRequest` (document_id, file_url, metadata, chunking_config)
- Response: `IngestResponse` (job_id, status="queued", estimated_time)
- Triggers async ingestion job

**`GET /rag/ingest/status/{job_id}`**
- Response: `IngestStatusResponse` (job_id, status, chunks_created, error)
- Poll to track progress

---

## Query Routes (`app/api/routes/query.py`)

**`POST /rag/query`**
- Request: `QueryRequest` (query, user_id, filters, retrieval_config, generation_config)
- Response: Streaming SSE
  - `{"type": "retrieval", "chunks": 5, "avg_score": 0.82}`
  - `{"type": "token", "content": "The refund..."}`
  - `{"type": "token", "content": " policy..."}`
  - `{"type": "sources", "sources": [{"doc": "policy.pdf", "page": 3}]}`
  - `{"type": "done"}`

---

## Bulk Routes (`app/api/routes/bulk.py`)

**`POST /rag/bulk-delete`**
- Delete by user_id or tag filter
- Useful for GDPR / data cleanup

**`POST /rag/reindex`**
- Migrate embeddings after model upgrade
- Batch re-embed with new model

**`DELETE /rag/documents/{doc_id}`**
- Delete single document + all chunks
