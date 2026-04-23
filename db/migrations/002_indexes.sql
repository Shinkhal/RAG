CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
  ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS ix_chunks_user_id
  ON chunks (user_id);

CREATE INDEX IF NOT EXISTS ix_chunks_document_id
  ON chunks (document_id);

CREATE INDEX IF NOT EXISTS ix_documents_user_id
  ON documents (user_id);

CREATE INDEX IF NOT EXISTS ix_ingest_jobs_user_status
  ON ingest_jobs (user_id, status);

CREATE INDEX IF NOT EXISTS ix_query_logs_user_created
  ON query_logs (user_id, created_at);

CREATE INDEX IF NOT EXISTS ix_personas_is_active
  ON personas (is_active);
