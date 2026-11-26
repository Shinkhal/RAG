# Database Schema

Migrations are tracked by filename and SHA-256 checksum in `schema_migrations`.
They are serialized with a PostgreSQL advisory transaction lock and an applied
migration cannot be silently edited. Development startup applies pending files;
production should run migrations as a deployment step before starting the API:

```bash
python -m app.db.migrate
```

**File:** `db/migrations/001_init.sql`

## Tables

### documents
See `db/migrations/001_init.sql`.

### chunks
See `db/migrations/001_init.sql`.

### ingest_jobs
See `db/migrations/001_init.sql`.

---

**File:** `db/migrations/002_indexes.sql`

See `db/migrations/002_indexes.sql`.

---

**File:** `db/migrations/003_rls.sql`

Row-level security policies to prevent cross-user data leakage live in
`db/migrations/003_rls.sql` and are intentionally not auto-applied on startup yet.

---

**File:** `db/migrations/005_chat_sessions.sql`

Adds `chat_sessions` and backfills/links `session_id` across `documents`,
`chunks`, and `ingest_jobs` with foreign keys and supporting indexes.

**File:** `db/migrations/006_chunks_full_text_search.sql`

Adds the GIN index used by PostgreSQL full-text candidate retrieval.

**File:** `db/migrations/007_durable_ingestion_and_chunk_identity.sql`

Adds ingestion leases and attempt counters, removes duplicate `(document_id,
chunk_idx)` rows, and makes that chunk identity unique for idempotent reindexing.
