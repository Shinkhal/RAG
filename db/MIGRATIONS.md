# Database Schema

The runtime startup path applies `001_init.sql` and `002_indexes.sql` automatically
when `DATABASE_URL` points at your Postgres instance.

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
