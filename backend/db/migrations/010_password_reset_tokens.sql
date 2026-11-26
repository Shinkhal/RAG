CREATE TABLE IF NOT EXISTS rag_password_reset_tokens (
  token_hash VARCHAR(64) PRIMARY KEY,
  account_id VARCHAR NOT NULL REFERENCES rag_accounts(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_rag_password_reset_tokens_account_id
  ON rag_password_reset_tokens (account_id);
CREATE INDEX IF NOT EXISTS ix_rag_password_reset_tokens_expires_at
  ON rag_password_reset_tokens (expires_at);
