CREATE DATABASE dashboard_db;

\c dashboard_db

CREATE TABLE IF NOT EXISTS analysis_records (
    id           TEXT PRIMARY KEY,
    repository   TEXT NOT NULL,
    sha          TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS analysis_findings (
    id          BIGSERIAL PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES analysis_records(id) ON DELETE CASCADE,
    position    INT NOT NULL,
    content     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ar_created_at  ON analysis_records (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ar_repo_sha    ON analysis_records (repository, sha);
CREATE INDEX IF NOT EXISTS idx_af_analysis_id ON analysis_findings (analysis_id);

CREATE TABLE IF NOT EXISTS replay_progress (
    repository   TEXT PRIMARY KEY,
    last_page    INTEGER NOT NULL,
    current_page INTEGER NOT NULL,
    page_index   INTEGER NOT NULL
);
