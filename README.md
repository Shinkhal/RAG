# RAG Microservice

NotebookLM-style Retrieval Augmented Generation (RAG) backend built with FastAPI.

## Stack

- FastAPI + Uvicorn
- PostgreSQL (`pgvector`) via SQLAlchemy async
- Gemini for embeddings and answer generation
- Redis (Upstash-compatible) for query caching
- Cloudflare R2 for document object storage

## Project Layout

- `app/` application code
- `db/` SQL migration notes and migration files
- `tests/` unit/integration test scaffolding
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

4. Run API:

```bash
uvicorn app.main:app --reload
```

Health check:

```text
GET /health
```

## Environment Variables

Core variables are listed in `.env.example`, including:

- `DATABASE_URL`
- `GEMINI_API_KEY`
- `REDIS_URL` and `REDIS_TOKEN`
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`

## API Endpoints (Current)

Base prefix: `/api/v1/rag`

- `POST /ingest`
- `GET /ingest/status/{job_id}`
- `GET /documents/{document_id}`
- `POST /query`
- `POST /query/stream`
- `DELETE /documents/{document_id}`
- `POST /bulk-delete`
- `POST /reindex/{document_id}` (placeholder)

## Makefile Commands

If you use `make`, available targets include:

- `make help`
- `make install`
- `make run`
- `make test`
- `make lint`
- `make format`
- `make typecheck`
- `make check`

## Notes

- Tests are scaffolded; test cases still need implementation.
- Some implementation areas are still in-progress.
