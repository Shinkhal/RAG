  # Observability & Operations

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
