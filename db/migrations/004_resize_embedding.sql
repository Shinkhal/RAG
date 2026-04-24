-- Drop the original HNSW index correctly by its actual name
DROP INDEX IF EXISTS ix_chunks_embedding_hnsw;

-- Drop the IVFFlat index we tried to create earlier, just in case
DROP INDEX IF EXISTS idx_chunks_embedding;

-- Then resize
ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(768);

-- Create IVFFlat index (no dimension limit)
CREATE INDEX idx_chunks_embedding ON chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
