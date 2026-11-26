# RAG Workspace

A standalone document Q&A app built with FastAPI. Create an account, organize documents into notebooks, and ask questions with source excerpts and saved conversation history.

## Stack

- **FastAPI + Uvicorn** - Async web framework
- **PostgreSQL (`pgvector`)** - Vector database via SQLAlchemy async
- **Gemini** - Embeddings and answer generation
- **Redis (Upstash-compatible)** - Query caching, document context memory
- **Cloudinary** - Durable, authenticated storage for new document uploads
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

- `backend/` FastAPI, retrieval, document ingestion, database migrations, and tests.
- `frontend/` React and TypeScript workspace built with Vite. FastAPI serves the production build on the same origin as the API.

## Quick Start

1. From the repository root, run `cd backend`, then create and activate a virtualenv.
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

5. Start the app:

```bash
uvicorn app.main:app --reload
```

For production, run `python -m app.db.migrate` once as a deployment step before
starting the API. Production startup checks database connectivity but does not
run schema changes. Ingestion jobs are stored in PostgreSQL and source uploads
are persisted to Cloudinary before the API returns `202`; all replicas can poll
the same leased job queue.

Uploads are bounded by `MAX_UPLOAD_SIZE_MB` (default 10 MB), with PDFs additionally
bounded by `MAX_PDF_SIZE_MB`. PDF metadata reports pages with no extractable text;
enable OCR to index scanned pages.
Set `ENABLE_PDF_OCR=true` to OCR pages without text. This requires the Python
packages in the dependency files and the Tesseract executable installed in the
worker image; OCR’d and still-unreadable page numbers are included in document
metadata.
When changing `EMBEDDING_MODEL`, reindex existing documents; vector search filters
out documents embedded with a different model until they are reindexed.

6. In a second terminal, run the React frontend from the repository root with Node.js 20.19+ or 22.12+.

```bash
cd frontend
npm ci
npm run dev
```

Open [the development workspace](http://localhost:5173/workspace). Vite proxies `/api` to FastAPI at `http://127.0.0.1:8000`. For a different backend address, set `RAG_API_TARGET` in `frontend/.env.local` and restart Vite.

If Vite reports `ECONNREFUSED 127.0.0.1:8000`, the API has not started listening.
Keep the backend terminal open and wait for `Application startup complete`.
Database connections time out after `DATABASE_CONNECT_TIMEOUT_SECONDS` (default 10)
instead of waiting indefinitely. If startup reports a database connection failure,
check `DATABASE_URL` and database/network availability; authenticated operations
require a working database even when the development server can serve pages.

For a single-port setup, run `npm ci` and `npm run build` from `frontend/`, then start FastAPI from `backend/`. FastAPI serves `frontend/dist/` at [http://127.0.0.1:8000/workspace](http://127.0.0.1:8000/workspace). Include the built frontend alongside the backend in your deployment.

Health check:

```text
GET /health
```

## Environment Variables

Core variables are listed in `.env.example`, including:

- `DATABASE_URL` (use the exact PostgreSQL connection string for your database)
- `GEMINI_API_KEY`
- `REDIS_URL` and `REDIS_TOKEN` (Redis protocol)
- `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` (optional Upstash REST alternative)
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET`
- `UPSTASH_VECTOR_REST_URL`, `UPSTASH_VECTOR_REST_TOKEN` (optional; not active in retrieval yet)
- `MAX_UPLOAD_SIZE_MB`, `MAX_UPLOADS_PER_HOUR`, `INGEST_WORKER_LEASE_MINUTES`
- `INGEST_WORKER_POLL_INTERVAL_SECONDS` (default `1`)

### Feature Flags

| Variable | Default | Description |
|----------|--------|-------------|
| `ENABLE_BM25` | `true` | Enable BM25 keyword search alongside vector similarity |
| `ENABLE_QUERY_REWRITING` | `false` | Enable LLM-based query rewriting for better retrieval |
| `ENABLE_RERANKING` | `false` | Enable cross-encoder reranking of retrieved chunks |
| `ENABLE_PARENT_CONTEXT` | `false` | Fetch parent document context around retrieved chunks |
| `PARENT_CONTEXT_WINDOW` | `2` | Number of chunks to fetch before/after each result |

## API Endpoints

Account routes use the `/api/v1/auth` prefix.

- `POST /signup` and `POST /login` accept email and password and set a session cookie.
- `GET /me` returns the signed-in account.
- `POST /logout` ends the current session.

Notebook, ingestion, and query routes use the `/api/v1/rag` prefix and derive ownership from the session cookie. Clients must send `X-RAG-Request: 1` on authenticated writes and on signup, login, and logout. Enable `APP_ENV=production` behind HTTPS for a secure session cookie.

Existing notebooks keep their original owner IDs. New accounts receive new IDs, so assigning existing notebooks to a new account requires an explicit data migration. Cloudinary files uploaded before this change retain their original delivery type.


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
- `GET /sessions/{session_id}/documents` - List the notebook’s sources and their processing status
- `GET /sessions/{session_id}/history` - Return the most recent 100 completed Q&A turns

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

## Notes

- Document context automatically cached in Redis during ingestion
- All feature flags default to sensible values for production use
- On startup the app connects to Postgres, applies schema migrations, and reports database state through `/health`
