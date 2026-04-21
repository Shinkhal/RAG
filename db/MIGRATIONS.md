# Database Schema

**File:** `db/migrations/001_init.sql`

## Tables

### documents
```sql
CREATE TABLE documents (
  id              TEXT PRIMARY KEY,
  user_id         TEXT NOT NULL,
  status          TEXT CHECK (status IN ('queued','processing','processed','failed')),
  chunks_created  INT DEFAULT 0,
  error           TEXT,
  embed_version   TEXT DEFAULT 'gemini-text-embedding-004',
  metadata        JSONB,
  processed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  expires_at      TIMESTAMPTZ DEFAULT NOW() + INTERVAL '90 days'
);
```

### chunks
```sql
CREATE TABLE chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id TEXT NOT NULL,
  user_id     TEXT NOT NULL,
  chunk_idx   INT,
  content     TEXT,
  embedding   vector(768),   -- Gemini dimensions
  metadata    JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### ingest_jobs
```sql
CREATE TABLE ingest_jobs (
  job_id        TEXT PRIMARY KEY,
  document_id   TEXT NOT NULL,
  user_id       TEXT NOT NULL,
  status        TEXT DEFAULT 'queued',
  chunks_created INT DEFAULT 0,
  error         TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

---

**File:** `db/migrations/002_indexes.sql`

```sql
-- Vector search index (HNSW)
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);

-- Filter indices
CREATE INDEX ON chunks (user_id);
CREATE INDEX ON chunks (document_id);
CREATE INDEX ON documents (user_id);
CREATE INDEX ON ingest_jobs (user_id, status);
```

---

**File:** `db/migrations/003_rls.sql`

Row-level security policies to prevent cross-user data leakage:
- `chunks`: users can only see chunks where user_id = auth.uid()
- `documents`: users can only see docs where user_id = auth.uid()
