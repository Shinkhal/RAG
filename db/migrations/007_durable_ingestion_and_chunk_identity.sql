ALTER TABLE ingest_jobs
  ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_ingest_jobs_locked_at ON ingest_jobs (locked_at);

WITH ranked AS (
  SELECT ctid, ROW_NUMBER() OVER (
    PARTITION BY document_id, chunk_idx ORDER BY created_at DESC, id DESC
  ) AS duplicate_rank
  FROM chunks
)
DELETE FROM chunks c USING ranked r
WHERE c.ctid = r.ctid AND r.duplicate_rank > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_chunks_document_chunk_idx
  ON chunks (document_id, chunk_idx);
