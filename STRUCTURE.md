# RAG Microservice - File Structure

## Project Layout

```
RAG/
├── app/                              # Main application package
│   ├── __init__.py
│   ├── main.py                      # FastAPI app factory
│   ├── core/                        # Configuration & constants
│   │   ├── __init__.py
│   │   └── config.py                # Settings + env vars
│   ├── api/                         # API routes & handlers
│   │   ├── __init__.py
│   │   ├── router.py                # Route aggregator
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── ingest.py            # POST /rag/ingest, GET /rag/ingest/status/{job_id}
│   │       ├── query.py             # POST /rag/query (streaming)
│   │       └── bulk.py              # POST /rag/bulk-delete, /rag/reindex
│   ├── schemas/                     # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── ingest.py                # IngestRequest, IngestResponse
│   │   └── query.py                 # QueryRequest, QueryResponse
│   ├── services/                    # Business logic layer
│   │   ├── __init__.py
│   │   ├── chunking.py              # Sliding window + batching
│   │   ├── ingestion.py             # Ingest job orchestration
│   │   ├── retrieval.py             # Vector similarity + reranking
│   │   ├── generation.py            # LLM routing + answer synthesis
│   │   └── security.py              # Prompt injection sanitizer
│   ├── clients/                     # External service adapters
│   │   ├── __init__.py
│   │   ├── gemini.py                # Gemini embed/LLM client
│   │   ├── supabase.py              # Supabase pgvector client
│   │   ├── redis_cache.py           # Upstash Redis client
│   │   └── r2.py                    # Cloudflare R2 client
│   ├── repositories/                # Data access layer (local + real)
│   │   ├── __init__.py
│   │   ├── in_memory.py             # Local stores for dev
│   │   ├── supabase_repo.py         # Prod Supabase impl
│   │   └── cache_repo.py            # Cache layer abstraction
│   └── workers/                     # Async job processing
│       ├── __init__.py
│       ├── queue.py                 # BullMQ / RQ abstraction
│       └── tasks/
│           ├── __init__.py
│           └── ingest_document.py   # Chunk + embed + store task
├── db/                              # Database migrations & schemas
│   ├── migrations/
│   │   ├── 001_init.sql             # Tables: documents, chunks, jobs
│   │   ├── 002_indexes.sql          # HNSW vector index, user_id idx
│   │   └── 003_rls.sql              # Row-level security policies
│   └── seeds.sql                    # Optional test data
├── tests/                           # Test suite
│   ├── conftest.py                  # Pytest fixtures
│   ├── unit/
│   │   ├── test_chunking.py
│   │   ├── test_sanitizer.py
│   │   ├── test_retrieval.py
│   │   └── test_generation.py
│   └── integration/
│       ├── test_ingest_e2e.py
│       ├── test_query_e2e.py
│       └── test_multiuser.py
├── ops/                             # Operations & observability
│   ├── prometheus.yml               # Grafana Cloud scrape config
│   ├── runbook.md                   # Incident response guide
│   ├── docker-compose.yml           # Local Supabase + Redis + S3
│   └── k6-load-test.js              # Load testing script
├── .env.example                     # Template env vars
├── .gitignore
├── pyproject.toml                   # Python dependencies & build config
├── Makefile                         # Dev commands (install, test, run, migrate)
└── README.md                        # Getting started guide
```

## Key Files to Create

### Configuration
- `pyproject.toml` – Poetry/pip dependencies
- `.env.example` – Environment variables template
- `Makefile` – Common commands

### Application Entry
- `app/main.py` – FastAPI app factory
- `app/core/config.py` – Settings from env

### API Contracts
- `app/schemas/ingest.py` – Ingest request/response
- `app/schemas/query.py` – Query request/response

### Service Layer
- `app/services/chunking.py` – Sliding window logic
- `app/services/ingestion.py` – Job orchestration
- `app/services/retrieval.py` – Vector search
- `app/services/generation.py` – LLM routing & answers
- `app/services/security.py` – Sanitizers

### Adapters (Providers)
- `app/clients/gemini.py` – Embeddings & LLM
- `app/clients/supabase.py` – Vector DB
- `app/clients/redis_cache.py` – Cache layer
- `app/clients/r2.py` – PDF storage

### Data Layer
- `app/repositories/in_memory.py` – Local dev store
- `app/repositories/supabase_repo.py` – Prod Supabase
- `app/workers/queue.py` – Job queue abstraction

### Database
- `db/migrations/001_init.sql` – Schema: documents, chunks, jobs
- `db/migrations/002_indexes.sql` – HNSW index
- `db/migrations/003_rls.sql` – Row-level security

### Tests & Ops
- `tests/unit/` – Unit tests for each service
- `tests/integration/` – E2E tests
- `ops/runbook.md` – Troubleshooting & recovery

