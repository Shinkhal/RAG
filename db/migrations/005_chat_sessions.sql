-- Add chat session support and connect existing entities to sessions.
-- This migration is intentionally idempotent because startup replays all migrations.

CREATE TABLE IF NOT EXISTS chat_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS session_id TEXT;

INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
SELECT DISTINCT
  'legacy-' || md5(d.user_id),
  d.user_id,
  'Legacy Session',
  NOW(),
  NOW()
FROM documents d
WHERE d.user_id IS NOT NULL
ON CONFLICT (id) DO NOTHING;

UPDATE documents
SET session_id = 'legacy-' || md5(user_id)
WHERE session_id IS NULL AND user_id IS NOT NULL;

ALTER TABLE documents ALTER COLUMN session_id SET NOT NULL;
ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_session_id;
ALTER TABLE documents
  ADD CONSTRAINT fk_documents_session_id
  FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE;

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS session_id TEXT;

UPDATE chunks c
SET session_id = d.session_id
FROM documents d
WHERE c.document_id = d.id AND c.session_id IS NULL;

ALTER TABLE chunks ALTER COLUMN session_id SET NOT NULL;
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS fk_chunks_session_id;
ALTER TABLE chunks
  ADD CONSTRAINT fk_chunks_session_id
  FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE;

ALTER TABLE ingest_jobs ADD COLUMN IF NOT EXISTS session_id TEXT;

UPDATE ingest_jobs j
SET session_id = d.session_id
FROM documents d
WHERE j.document_id = d.id AND j.session_id IS NULL;

ALTER TABLE ingest_jobs ALTER COLUMN session_id SET NOT NULL;
ALTER TABLE ingest_jobs DROP CONSTRAINT IF EXISTS fk_ingest_jobs_session_id;
ALTER TABLE ingest_jobs
  ADD CONSTRAINT fk_ingest_jobs_session_id
  FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id
  ON chat_sessions (user_id);

CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_created
  ON chat_sessions (user_id, created_at);

CREATE INDEX IF NOT EXISTS ix_documents_session_id
  ON documents (session_id);

CREATE INDEX IF NOT EXISTS ix_chunks_session_id
  ON chunks (session_id);
