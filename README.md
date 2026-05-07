# RAG Microservice

NotebookLM-style Retrieval Augmented Generation (RAG) backend built with FastAPI. Features context memory for document summarization and hybrid search optimization (BM25, query rewriting, reranking).

## Stack

- **FastAPI + Uvicorn** - Async web framework
- **PostgreSQL (`pgvector`)** - Vector database via SQLAlchemy async
- **Gemini** - Embeddings and answer generation
- **Redis (Upstash-compatible)** - Query caching, document context memory
- **Cloudflare R2** - Document object storage
- **BM25 + Cross-Encoder** - Hybrid search optimization
- **Sentence-Transformers** - Reranking with ms-marco-MiniLM

## Features

### Context Memory (Summarization)
- Automatic document context caching during ingestion
- Support for "Summarize this document", "Brief overview", "TL;DR" queries
- Persona-styled summaries

### Hybrid Search
- **Vector similarity** - pgvector cosine similarity
- **BM25 keyword search** - Lexical fallback for better recall
- **Reciprocal Rank Fusion** - Combines vector + BM25 scores
- **Query rewriting** - LLM-based query expansion
- **Cross-Encoder reranking** - Improves relevance with ms-marco-MiniLM
- **Parent document retrieval** - Fetches surrounding context

## Project Layout

- `app/` application code
  - `app/services/retrieval.py` - Hybrid search with BM25, RRF, reranking
  - `app/services/ingestion.py` - Document processing with context caching
- `db/` SQL migration notes and migration files
- `tests/` unit/integration tests (120+ tests passing)
- `ops/` operational notes and infra config

## Quick Start

1. Create and activate virtualenv.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy env template and set secrets:

```bash
cp .env.example .env
```

4. Configure feature flags in `.env` (optional):

```bash
# RAG Optimizations (defaults shown)
ENABLE_BM25=true              # BM25 keyword search
ENABLE_QUERY_REWRITING=false  # LLM query rewriting
ENABLE_RERANKING=false        # Cross-encoder reranking
ENABLE_PARENT_CONTEXT=false    # Parent document context
PARENT_CONTEXT_WINDOW=2        # Chunks before/after each result
```

5. Run API:

```bash
uvicorn app.main:app --reload
```

Health check:

```text
GET /health
```

## Environment Variables

Core variables are listed in `.env.example`, including:

- `DATABASE_URL` (use the exact PostgreSQL connection string for your database)
- `GEMINI_API_KEY`
- `REDIS_URL` and `REDIS_TOKEN` (Redis protocol)
- `REDIS_REST_URL` and `REDIS_REST_TOKEN` (Upstash REST fallback)
- `UPSTASH_VECTOR_REST_URL`, `UPSTASH_VECTOR_REST_TOKEN` (optional; not active in retrieval yet)
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`
- `PERSONA_ADMIN_TOKEN` (required for admin persona CRUD endpoints)

### Feature Flags

| Variable | Default | Description |
|----------|--------|-------------|
| `ENABLE_BM25` | `true` | Enable BM25 keyword search alongside vector similarity |
| `ENABLE_QUERY_REWRITING` | `false` | Enable LLM-based query rewriting for better retrieval |
| `ENABLE_RERANKING` | `false` | Enable cross-encoder reranking of retrieved chunks |
| `ENABLE_PARENT_CONTEXT` | `false` | Fetch parent document context around retrieved chunks |
| `PARENT_CONTEXT_WINDOW` | `2` | Number of chunks to fetch before/after each result |

## API Endpoints

Base prefix: `/api/v1/rag`

### Ingestion & Document Management
- `POST /ingest` - Upload and process documents
- `GET /ingest/status/{job_id}` - Check ingestion status
- `GET /documents/{document_id}` - Get document metadata
- `DELETE /documents/{document_id}` - Delete document
- `POST /bulk-delete` - Delete multiple documents

### Query & Generation
- `POST /query` - RAG query with hybrid search
- `POST /query/stream` - Streaming response
- **New**: Supports summarization queries ("Summarize this document", "Brief overview", "TL;DR")

### Personas (AI Personalities)
- `GET /personas` - List available personas
- `GET /personas/{persona_id}` - Get persona details
- `POST /admin/personas` - Create persona (admin)
- `PUT /admin/personas/{persona_id}` - Update persona (admin)
- `DELETE /admin/personas/{persona_id}` - Delete persona (admin)

### Chat Sessions
- `POST /sessions` - Create chat session
- `GET /sessions` - List user sessions
- `GET /sessions/{session_id}` - Get session details
- `DELETE /sessions/{session_id}` - Delete session

## Makefile Commands

If you use `make`, available targets include:

- `make help`
- `make install`
- `make run`
- `make test`
- `make lint` - Run ruff linter
- `make format` - Format code with ruff
- `make typecheck` - Run mypy type checker
- `make check` - Run lint + typecheck

## Test Results

- ✅ **120+ unit tests passing**
- ✅ **Ruff linting** - 0 errors
- ✅ **Hybrid search** - Vector + BM25 + RRF
- ✅ **Context memory** - Document summarization support

## Notes

- Production-ready with robust retrieval optimizations
- Document context automatically cached in Redis during ingestion
- All feature flags default to sensible values for production use
- On startup the app connects to Postgres, applies schema migrations, and reports database state through `/health`
