CREATE DATABASE analysis_db;

\c analysis_db

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS past_findings (
    id          BIGSERIAL PRIMARY KEY,
    rule_text   TEXT        NOT NULL,
    context     TEXT        NOT NULL,
    embedding   vector(768) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS past_findings_embedding_idx
    ON past_findings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
