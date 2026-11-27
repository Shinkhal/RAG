  # Observability & Operations

## Logs

The service writes one line per log record to stdout and, unless `LOG_TO_FILE=false`, appends to a rotating file. File logs survive restarts and crashes; stdout is still the source of truth for container and systemd collectors.

- Location: `LOG_DIR` / `LOG_FILENAME` (default `backend/logs/rag.log`).
- Rotation: `LOG_MAX_BYTES` per file (default 10 MB) with `LOG_BACKUP_COUNT` rotated files (default 5).
- Format: `LOG_FORMAT=json` for production aggregation, `text` for local development.
- Correlation: every request is logged with a sanitized `X-Request-ID`, echoed in the response header and included in every record emitted during that request.
- Access logs: one line per request (`GET /api/v1/rag/query -> 200 in 42.10ms`) with `method`, `path`, `status_code`, `duration_ms`, and `client_ip`. `/health` and static assets are skipped.
- Uvicorn's access logger is disabled to avoid duplicate lines; uvicorn startup and error logs use the same formatter and file.
- Multiple uvicorn workers share one file handler, which can interleave lines and race on rotation. For `--workers > 1`, prefer `LOG_TO_FILE=false` and collect stdout with your platform's log driver (or run a dedicated sidecar), keeping `LOG_FORMAT=json`.

## Metrics (Prometheus → Grafana Cloud)

### Query Performance
- `rag_query_latency_p50` – target < 1s
- `rag_query_latency_p95` – target < 2s
- `rag_query_latency_p99` – target < 5s
- `rag_cache_hit_rate` – target > 50%

### Retrieval Quality
- `rag_citation_present_ratio` – target 100%
- `rag_avg_chunk_score` – track coverage

### Ingestion
- `rag_ingest_chunks_per_doc` – throughput
- `rag_ingest_failure_rate` – target < 5%

### Vector DB
- `rag_pgvector_query_latency` – alert > 300ms
- `rag_hnsw_index_size` – plan for 2M+ vectors

### Cost
- `rag_gemini_spend_usd` – alert > $80/mo
- `rag_cost_per_query_usd` – target < $0.01

---

## Runbook (`ops/runbook.md`)

Covers:
- pgvector slow at 2M+ vectors → migrate to Qdrant Cloud
- Gemini embedding model change → version all embeddings
- Supabase outage → fallback to FTS
- Gemini API downtime → route to Claude/GPT-4o-mini
- Poor chunk quality → A/B test chunking
- Data leakage → audit RLS policies
- Cost spike → throttle, increase cache hit rate

---

## Docker Compose (`ops/docker-compose.yml`)

Local dev setup:
- Supabase (pgvector)
- Redis
- S3 (MinIO)
- Optional: K6 load tester

---

## Makefile Commands

```
make install      # pip install -e .[dev]
make test         # pytest -q
make test-cov     # pytest --cov
make run          # uvicorn app.main:app --reload
make migrate      # Apply db migrations
make load-test    # k6 run ops/k6-load-test.js
```
