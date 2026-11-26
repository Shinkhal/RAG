CREATE TABLE IF NOT EXISTS rag_accounts (
  id VARCHAR PRIMARY KEY,
  email VARCHAR(254) NOT NULL UNIQUE,
  password_salt VARCHAR(32) NOT NULL,
  password_hash VARCHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_login_sessions (
  token_hash VARCHAR(64) PRIMARY KEY,
  account_id VARCHAR NOT NULL REFERENCES rag_accounts(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_rag_login_sessions_account_id ON rag_login_sessions (account_id);
CREATE INDEX IF NOT EXISTS ix_rag_login_sessions_expires_at ON rag_login_sessions (expires_at);

CREATE TABLE IF NOT EXISTS rag_conversation_turns (
  id SERIAL PRIMARY KEY,
  session_id VARCHAR NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  question TEXT NOT NULL,
  response JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_rag_conversation_turns_session_id ON rag_conversation_turns (session_id);
