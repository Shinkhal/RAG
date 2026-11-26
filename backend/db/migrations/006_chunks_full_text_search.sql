-- Support lexical candidate retrieval across a chat session.
CREATE INDEX IF NOT EXISTS ix_chunks_content_fts
  ON chunks USING GIN (to_tsvector('simple', content));
