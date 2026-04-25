# 📄 RAG + Persona Microservice — PRD (As-Built)

## Reflecting the Actual Implementation

---

## 🎯 Mission

A **NotebookLM-style RAG microservice** with **persona-based responses**:

- Upload documents (PDF, TXT, MD, CSV) → chat with them
- Responses are styled by a selected persona (Einstein, Newton, SRK, etc.)
- Free tier (Gemini) + paid tiers (OpenAI, Anthropic)
- Admins manage a persona library; users select per query
- Chat sessions group documents and queries together

---

## 🧩 Core Concept

```
User creates a chat session
   ↓
Uploads PDF about quantum physics
   ↓
PDF stored on Cloudinary, chunks embedded via Gemini
   ↓
Selects "Einstein" persona
   ↓
Asks: "What is entanglement?"
   ↓
RAG retrieves context from pgvector (hybrid similarity + keyword boost)
   ↓
LLM generates a persona-styled, grounded answer in a single pass
   ↓
Response: "Imagine, if you will, two particles dancing
           in perfect harmony across the cosmos..."
```

**Key principle:** Grounding > Style — persona never distorts facts.

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────┐
│           RAG Microservice (FastAPI)          │
│                                              │
│  ┌─────────────┐     ┌──────────────────┐   │
│  │  Ingestion   │     │  Query Pipeline  │   │
│  │  Pipeline    │     │  (retrieve →     │   │
│  │  (upload →   │     │   generate)      │   │
│  │   chunk →    │     └───────┬──────────┘   │
│  │   embed)     │             │              │
│  └──────┬───────┘     ┌───────▼──────────┐   │
│         │             │   LLM Router     │   │
│  ┌──────▼───────┐     │  (tier-based)    │   │
│  │  Cloudinary  │     └───────┬──────────┘   │
│  │  (raw file   │             │              │
│  │   storage)   │    ┌────────┼──────────┐   │
│  └──────────────┘    ▼        ▼          ▼   │
│               ┌────────┐ ┌────────┐ ┌──────┐ │
│               │ Gemini │ │ OpenAI │ │Claude│ │
│               │ (free) │ │ (pro)  │ │(ent.)│ │
│               └────────┘ └────────┘ └──────┘ │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │   PostgreSQL + pgvector (Supabase)   │    │
│  │   • Documents, Chunks, Embeddings    │    │
│  │   • Chat Sessions, Personas          │    │
│  │   • Ingest Jobs, Query Logs          │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │   Redis / Upstash                    │    │
│  │   • Query cache   • Rate limiting    │    │
│  │   • Persona cache • Document cache   │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

---

## 🎭 Persona System

### Persona Storage

Personas are stored in the **PostgreSQL `personas` table** (not a separate service). Default personas are seeded from JSON config files at `app/personas/configs/` on startup.

**Example persona config (`einstein.json`):**

```json
{
  "persona_id": "einstein",
  "name": "Albert Einstein Style",
  "description": "Reflective, analogy-driven explanation style inspired by Einstein",
  "intensity": 0.7,
  "is_active": true,
  "is_system": true,
  "created_by": "system",
  "style_config": {
    "tone": "reflective, curious, thoughtful",
    "voice": "calm, insightful, slightly philosophical",
    "rules": [
      "Use simple analogies to explain complex ideas",
      "Break down concepts into intuitive mental models",
      "Avoid jargon unless necessary"
    ],
    "do": [
      "Use phrases like 'Imagine if...' or 'Think of it as...'",
      "Guide the reader step by step"
    ],
    "dont": [
      "Do not exaggerate or dramatize",
      "Do not change factual meaning"
    ],
    "formatting": {
      "style": "paragraph",
      "use_analogies": true,
      "max_length": "medium"
    }
  }
}
```

### Default Personas (Shipped)

| Persona ID     | Name                  |
| -------------- | --------------------- |
| `einstein`     | Albert Einstein Style |
| `newton`       | Isaac Newton Style    |
| `jacke`        | Jackie Chan Style     |
| `ronaldo`      | Cristiano Ronaldo     |
| `salman_khan`  | Salman Khan Style     |
| `srk`          | Shah Rukh Khan Style  |

### Persona Application

Persona styling is applied in a **single-pass prompt** — the LLM is instructed to produce a grounded factual answer _and_ apply the persona's style rules simultaneously. This avoids the latency of a two-step generation pipeline.

The `build_grounded_prompts()` function in `app/llms/prompts.py` renders the persona's `style_config` (tone, voice, rules, do/don't, formatting) into the system prompt and controls intensity.

---

## 🔄 Data Flows

### 1. Document Ingestion

```
User uploads quantum_physics.pdf via POST /ingest
   ↓
Validate file size (MAX_PDF_SIZE_MB, default 10MB)
   ↓
File stored on Cloudinary (raw resource)
   ↓
PDF → extract pages (PyPDF2)
   ↓
Pages → chunks (RecursiveCharacterTextSplitter, 300-500 chars + overlap)
   ↓
Chunks → embeddings (Gemini gemini-embedding-2, 768 dims)
   ↓
Embeddings + chunks stored in PostgreSQL pgvector
   ↓
Ingest job status tracked in ingest_jobs table
```

**Non-PDF files** (TXT, MD, CSV) follow the same pipeline using plain-text extraction with a sliding-window chunker.

### 2. Query with Persona

```
User: "What is quantum entanglement?"
Session: "session_abc"
Persona: "einstein"
Tier: "free" (Gemini)
   ↓
Check Redis cache for identical query
   ↓  (miss)
Embed query via Gemini (RETRIEVAL_QUERY task type)
   ↓
pgvector cosine similarity search (top_k × 4 oversampling)
   ↓
Hybrid scoring: cosine similarity + keyword boost + topic overlap
   ↓
Deduplication → top_k results
   ↓
Prompt injection sanitization on retrieved chunks
   ↓
Build grounded prompt with persona rules
   ↓
LLM generates answer (streaming or non-streaming)
   ↓
Cache result in Redis
   ↓
Log query to query_logs table
   ↓
Return answer + source citations
```

### 3. External Knowledge Fallback

When local context is insufficient, the system can optionally query the **Tavily API** for supplementary web results, which are appended as an "External Knowledge" section in the prompt.

---

## 📡 API Specification

### Base: `/api/v1/rag`

### Ingestion & Document Management

| Endpoint                      | Method   | Description                                                  |
| ----------------------------- | -------- | ------------------------------------------------------------ |
| `/ingest`                     | `POST`   | Upload a document, extract text, embed, store in pgvector    |
| `/ingest/status/{job_id}`     | `GET`    | Check ingestion job status (queued/processing/processed/failed) |
| `/documents/{document_id}`    | `GET`    | Get document metadata and status                             |
| `/documents/{document_id}`    | `DELETE` | Delete document, its chunks, and Cloudinary asset            |
| `/bulk-delete`                | `POST`   | Delete multiple documents at once                            |
| `/reindex/{document_id}`      | `POST`   | Re-index an existing document (placeholder)                  |

### Query & Generation

| Endpoint        | Method | Description                                              |
| --------------- | ------ | -------------------------------------------------------- |
| `/query`        | `POST` | RAG query: retrieve context → persona-styled answer      |
| `/query/stream` | `POST` | Same as `/query` with SSE streaming (`text/event-stream`)|

### Personas

| Endpoint                         | Method   | Description                          |
| -------------------------------- | -------- | ------------------------------------ |
| `/personas`                      | `GET`    | List all active personas             |
| `/personas/{persona_id}`         | `GET`    | Get a specific persona's details     |
| `/admin/personas`                | `POST`   | Create a new persona (admin)         |
| `/admin/personas/{persona_id}`   | `PUT`    | Update a persona (admin)             |
| `/admin/personas/{persona_id}`   | `DELETE` | Delete a persona (admin)             |

### Chat Sessions

| Endpoint                      | Method   | Description                     |
| ----------------------------- | -------- | ------------------------------- |
| `/sessions`                   | `POST`   | Create a new chat session       |
| `/sessions`                   | `GET`    | List all sessions for a user    |
| `/sessions/{session_id}`      | `GET`    | Get session details             |
| `/sessions/{session_id}`      | `DELETE` | Delete a session (cascades)     |

### Health & Root

| Endpoint   | Method | Description                                            |
| ---------- | ------ | ------------------------------------------------------ |
| `/health`  | `GET`  | Service health (DB, Cloudinary, Redis status)          |
| `/`        | `GET`  | Welcome message, uptime, environment, version          |

---

## 🗄️ Data Models (PostgreSQL + pgvector)

### Schema

```sql
-- Chat Sessions
CREATE TABLE chat_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Documents
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  session_id TEXT REFERENCES chat_sessions(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'queued',
  chunks_created INT DEFAULT 0,
  error TEXT,
  embed_version TEXT DEFAULT 'gemini-embedding-001',
  metadata JSONB DEFAULT '{}',
  processed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ
);

-- Chunks (with pgvector embeddings)
CREATE TABLE chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
  session_id TEXT REFERENCES chat_sessions(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL,
  chunk_idx INT NOT NULL,
  content TEXT NOT NULL,
  embedding VECTOR(768),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ingest Jobs
CREATE TABLE ingest_jobs (
  job_id TEXT PRIMARY KEY,
  document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
  session_id TEXT REFERENCES chat_sessions(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL,
  status TEXT DEFAULT 'queued',
  chunks_created INT DEFAULT 0,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- Query Logs
CREATE TABLE query_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  query TEXT,
  persona_id TEXT,
  answer TEXT,
  sources JSONB,
  llm_provider TEXT,
  tokens_used INT,
  latency_ms INT,
  cached BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Personas
CREATE TABLE personas (
  persona_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  style_config JSONB NOT NULL,
  intensity FLOAT DEFAULT 0.7,
  sample_responses JSONB,
  is_active BOOLEAN DEFAULT TRUE,
  is_system BOOLEAN DEFAULT FALSE,
  created_by TEXT,
  version INT DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🤖 LLM Routing (Subscription Tiers)

### Tier Configuration (Implemented)

```python
LLM_TIERS = {
    "free": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",        # env: FREE_TIER_MODEL
        "queries_per_day": 50,
        "max_tokens": 2000,
    },
    "pro": {
        "provider": "openai",
        "model": "gpt-4o-mini",              # env: PRO_TIER_MODEL
        "queries_per_day": 500,
        "max_tokens": 4000,
    },
    "enterprise": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022", # env: ENTERPRISE_TIER_MODEL
        "queries_per_day": -1,               # unlimited
        "max_tokens": 8000,
    },
}
```

### Routing Logic

Each tier has a dedicated LLM client class implementing `BaseLLMClient`:

| Tier         | Class                      | Provider  |
| ------------ | -------------------------- | --------- |
| Free         | `FreeTierGeminiLLM`        | Gemini    |
| Pro          | `ProTierOpenAILLM`         | OpenAI    |
| Enterprise   | `EnterpriseTierAnthropicLLM` | Anthropic |

All three share a common `build_grounded_prompts()` function for consistent prompt construction.

---

## 💰 Subscription Model

| Tier           | LLM                           | Queries/day | Personas | Price  |
| -------------- | ----------------------------- | ----------- | -------- | ------ |
| **Free**       | Gemini 2.5 Flash              | 50          | All 6    | $0     |
| **Pro**        | GPT-4o-mini                   | 500         | All 6    | $10/mo |
| **Enterprise** | Claude 3.5 Sonnet             | Unlimited   | All 6    | $50/mo |

---

## 🔍 Retrieval Pipeline

### Hybrid Scoring

The retrieval pipeline uses a multi-signal scoring approach:

1. **Cosine similarity** via pgvector (`<=>` operator)
2. **Keyword boost**: +0.05 per matching query word found in chunk text
3. **Topic overlap**: ratio of shared meaningful words between query and chunk
4. **Combined score**: `cosine_score × (1 + topic_overlap)`

### Oversampling & Deduplication

- Retrieves `top_k × 4` candidates from pgvector
- Deduplicates by first-400-chars prefix
- Returns final `top_k` results

### Low-Confidence Detection

If the best chunk's topic overlap is below a configurable threshold (default 0.15), the result is flagged as `low_confidence`, triggering an optional external knowledge fallback.

---

## 🚨 Guardrails

### Prompt Injection Defense (Implemented)

```python
BANNED_PATTERNS = [
    r"ignore (previous|above|all)",
    r"you are now",
    r"system:",
    r"<\|.*?\|>",
    r"disregard",
    r"forget (everything|all|previous)",
]
```

All retrieved chunks are sanitized before being passed to the LLM.

### Factual Validation (Implemented)

```python
def validate_persona_response(original: str, personafied: str) -> str:
    original_facts = set(extract_facts(original))
    persona_facts = set(extract_facts(personafied))
    missing_facts = original_facts - persona_facts
    if missing_facts and len(missing_facts) > len(original_facts) * 0.2:
        return original  # Fallback to factual
    return personafied
```

### Rate Limiting (Implemented)

- **Middleware-level**: IP-based rate limiting via Redis (`RateLimitMiddleware`)
- **Tier-aware**: Limits extracted from bearer token prefix (`ent_`, `pro_`, default free)
- **Upstash integration**: Sliding window rate limiter when Upstash SDK is available
- **Per-endpoint**: Ingestion endpoint excluded from global rate limits

---

## ⚙️ Tech Stack (Actual)

| Layer                | Tool                        | Notes                           |
| -------------------- | --------------------------- | ------------------------------- |
| **API**              | FastAPI + Uvicorn            | Async, with CORS + middleware  |
| **Language**         | Python 3.11+                | Type hints, async/await        |
| **Database**         | PostgreSQL + pgvector        | Supabase-hosted, port 6543     |
| **ORM**              | SQLAlchemy 2.0 (async)       | Mapped columns, relationships  |
| **Vector Search**    | pgvector extension           | 768-dim, cosine distance       |
| **Embeddings**       | Gemini `gemini-embedding-2`  | 768 dims, L2-normalized        |
| **LLM (Free)**       | Gemini 2.5 Flash             | Google GenAI SDK               |
| **LLM (Pro)**        | OpenAI GPT-4o-mini           | httpx-based client             |
| **LLM (Enterprise)** | Claude 3.5 Sonnet           | httpx-based client             |
| **File Storage**     | Cloudinary                   | Raw resource uploads           |
| **Cache**            | Redis (Upstash REST)         | Query, persona, document cache |
| **Rate Limiting**    | Upstash Ratelimit + Redis    | Sliding window                 |
| **PDF Parsing**      | PyPDF2                       | Page-level text extraction     |
| **Text Splitting**   | LangChain TextSplitters      | RecursiveCharacterTextSplitter |
| **External Search**  | Tavily API                   | Optional web fallback          |
| **Retry Logic**      | Tenacity + manual backoff    | Gemini 429 handling            |
| **Linting**          | Ruff                         | E, F, I, N, W rules           |
| **Type Checking**    | mypy (strict)                | Full app coverage              |
| **Testing**          | pytest + pytest-asyncio      | Scaffolded, needs expansion    |

---

## 📂 Project Structure

```
RAG/
├── app/
│   ├── main.py                   # FastAPI app, lifespan, health checks
│   ├── api/
│   │   ├── router.py             # Main API router
│   │   └── routes/
│   │       ├── ingest.py         # Document ingestion endpoints
│   │       ├── query.py          # RAG query endpoints
│   │       ├── persona.py        # Persona CRUD endpoints
│   │       ├── sessions.py       # Chat session endpoints
│   │       └── bulk.py           # Bulk delete endpoint
│   ├── clients/
│   │   ├── gemini.py             # Gemini embedding + generation client
│   │   ├── cloudinary_storage.py # Cloudinary upload/delete client
│   │   ├── redis_cache.py        # Redis cache (REST + native modes)
│   │   └── r2.py                 # Cloudflare R2 client (unused)
│   ├── config/
│   │   ├── env_config.py         # All environment settings
│   │   ├── cloudinary_config.py  # Cloudinary SDK init
│   │   ├── redis_config.py       # Redis connection manager
│   │   └── postgres_config.py    # DB URL helper
│   ├── core/
│   │   ├── middleware.py         # Request logging middleware
│   │   └── redis_keys.py        # Centralized Redis key patterns
│   ├── db/
│   │   ├── database.py           # SQLAlchemy async engine + sessions
│   │   └── models.py             # ORM models (6 tables)
│   ├── llms/
│   │   ├── base.py               # BaseLLMClient ABC
│   │   ├── router.py             # Tier → LLM client routing
│   │   ├── prompts.py            # Grounded prompt builder
│   │   ├── free.py               # Gemini LLM client
│   │   ├── pro.py                # OpenAI LLM client
│   │   └── enterprise.py         # Anthropic LLM client
│   ├── middleware/
│   │   └── rate_limit.py         # Rate limiting middleware
│   ├── personas/
│   │   └── configs/              # Default persona JSON files (6)
│   ├── repositories/
│   │   ├── supabase_repo.py      # Main data access layer
│   │   └── in_memory.py          # In-memory repo (testing)
│   ├── schemas/
│   │   ├── ingest.py             # Ingestion request/response schemas
│   │   ├── query.py              # Query request/response schemas
│   │   ├── persona.py            # Persona schemas
│   │   └── error.py              # Error response schema
│   ├── services/
│   │   ├── ingestion.py          # Document processing pipeline
│   │   ├── retrieval.py          # Hybrid vector search
│   │   ├── generation.py         # LLM answer generation
│   │   ├── chunking.py           # Text extraction & splitting
│   │   ├── personas.py           # Default persona seeding
│   │   ├── security.py           # Sanitization & validation
│   │   └── external_knowledge.py # Tavily web search fallback
│   ├── utils/
│   │   └── logger.py             # Logging config
│   └── workers/
│       ├── queue.py              # Async task queue
│       └── tasks/                # Background task definitions
├── db/
│   ├── migrations/               # SQL migration files
│   └── seeds.sql                 # Seed data
├── tests/                        # Test scaffolding
├── ops/                          # Operational notes
├── run.py                        # Windows task runner
├── Makefile                      # Unix task runner
├── pyproject.toml                # Project config & dependencies
├── requirements.txt              # Pip dependencies
└── .env                          # Environment variables
```

---

## 📏 Functional Requirements

### Implemented ✅

- [x] Multi-document upload per user (PDF, TXT, MD, CSV)
- [x] File size validation (configurable `MAX_PDF_SIZE_MB`)
- [x] Chat session management (create, list, delete)
- [x] Session-scoped document and chunk isolation
- [x] Persona-styled responses (6 default personas)
- [x] Admin persona CRUD (create, update, delete)
- [x] Source citations in answers
- [x] Streaming responses (SSE `text/event-stream`)
- [x] Query caching (Redis with configurable TTL)
- [x] Persona caching (Redis)
- [x] Rate limiting (middleware + Upstash sliding window)
- [x] Prompt injection defense
- [x] Multi-LLM routing (Gemini / OpenAI / Anthropic)
- [x] External knowledge fallback (Tavily)
- [x] Health check endpoint (DB + Cloudinary + Redis)
- [x] Exponential backoff for Gemini 429 errors
- [x] Request logging middleware
- [x] Bulk document deletion
- [x] Query logging to database

### Not Yet Implemented ❌

- [ ] Multi-persona conversations
- [ ] Persona mixing (e.g., Einstein 70% + Feynman 30%)
- [ ] Voice synthesis
- [ ] Analytics dashboard
- [ ] Reindex endpoint (placeholder exists)
- [ ] Full test suite (scaffolded only)

---

## 📊 Success Metrics

### Retrieval Quality

- Hybrid scoring (cosine + keyword + topic overlap)
- Low-confidence detection with configurable threshold
- Deduplication of near-identical chunks

### Performance

- Configurable `DEFAULT_TOP_K` (default 10)
- 4× oversampling for better recall
- Redis query caching (default 1h TTL)
- Batch embedding with rate-limit retry

### Observability

- Query logs persisted to PostgreSQL
- Request logging middleware
- Structured health checks
- Configurable `LOG_LEVEL`

---

## ⚡ Key Configuration (Environment Variables)

| Variable                       | Default                         | Description                    |
| ------------------------------ | ------------------------------- | ------------------------------ |
| `DATABASE_URL`                 | required                        | PostgreSQL connection string   |
| `GEMINI_API_KEY`               | required                        | Google Gemini API key          |
| `OPENAI_API_KEY`               | optional                        | OpenAI API key (pro tier)      |
| `ANTHROPIC_API_KEY`            | optional                        | Anthropic key (enterprise)     |
| `UPSTASH_REDIS_REST_URL`       | optional                        | Upstash Redis REST endpoint    |
| `UPSTASH_REDIS_REST_TOKEN`     | optional                        | Upstash Redis auth token       |
| `CLOUDINARY_CLOUD_NAME`        | optional                        | Cloudinary cloud name          |
| `CLOUDINARY_API_KEY`           | optional                        | Cloudinary API key             |
| `CLOUDINARY_API_SECRET`        | optional                        | Cloudinary API secret          |
| `TAVILY_API_KEY`               | optional                        | Tavily search API key          |
| `FREE_TIER_MODEL`              | `gemini-2.5-flash`              | Free tier LLM model            |
| `PRO_TIER_MODEL`               | `gpt-4o-mini`                   | Pro tier LLM model             |
| `ENTERPRISE_TIER_MODEL`        | `claude-3-5-sonnet-20241022`    | Enterprise tier LLM model      |
| `EMBEDDING_MODEL`              | `gemini-embedding-2`            | Embedding model name           |
| `EMBEDDING_OUTPUT_DIMENSIONALITY` | `768`                        | Embedding vector dimensions    |
| `MAX_CHUNK_SIZE`               | `500`                           | Max chars per chunk            |
| `CHUNK_OVERLAP`                | `20`                            | Overlap chars between chunks   |
| `EMBEDDING_BATCH_SIZE`         | `100`                           | Batch size for embedding calls |
| `DEFAULT_TOP_K`                | `5`                             | Default retrieval top-k        |
| `MIN_RETRIEVAL_SCORE`          | `0.5`                           | Min cosine similarity score    |
| `QUERY_CACHE_TTL_SECONDS`      | `3600`                          | Redis query cache TTL          |
| `MAX_PDF_SIZE_MB`              | `10`                            | Max upload file size           |
| `MAX_PDF_UPLOADS_PER_HOUR`     | `20`                            | Upload rate limit              |
| `APP_ENV`                      | `development`                   | App environment                |
| `LOG_LEVEL`                    | `INFO`                          | Logging level                  |
| `PORT`                         | `8000`                          | Server port                    |

---

## 🎓 Design Principles

> **1. Grounding > Style** — Persona never distorts facts; citations always preserved
> **2. Single-Pass Generation** — Persona + grounding in one LLM call for lower latency
> **3. Transparent Attribution** — Clear source citations with doc name, page, chunk ID
> **4. Tier Fairness** — Free tier is fully functional with all personas
> **5. Observable** — Query logs, request logging, health checks
> **6. Defensive** — Prompt injection sanitization on all retrieved context

---

## ✅ Definition of Done (Current State)

- [x] User can upload PDFs, TXT, MD, CSV
- [x] Chat works with session-scoped context
- [x] 6 personas available (all tiers)
- [x] Responses are grounded with citations
- [x] Streaming responses work via SSE
- [x] Rate limiting enforced
- [x] Query caching operational
- [x] Multi-LLM routing functional
- [x] Health check covers all services
- [ ] Full test coverage
- [ ] Production deployment on Railway
- [ ] Analytics dashboard

---

As-built PRD reflecting the actual implementation. System is functional with Gemini embeddings, pgvector search, Cloudinary storage, Redis caching, and 3-tier LLM routing.
