-- JobPilot Autopilot database schema (SQLite)
-- See docs/AUTOPILOT_PLAN.md section 13 for the full data model.

-- Schema version tracking for migrations
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Discovered jobs (deduplication + history)
CREATE TABLE IF NOT EXISTS discovered_jobs (
    job_id          TEXT PRIMARY KEY,        -- LinkedIn unique job ID
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    company_id      TEXT,
    location        TEXT,
    workplace_type  TEXT,                    -- remote/hybrid/onsite
    apply_method    TEXT,                    -- easy_apply/external
    external_url    TEXT,
    description     TEXT,
    requirements    TEXT,                    -- JSON array
    score           REAL,
    score_reasons   TEXT,                    -- JSON
    deal_breakers   TEXT,                    -- JSON array
    missing_skills  TEXT,                    -- JSON array
    recommendation  TEXT,                    -- strong_match/good/partial/skip
    recruiter_name  TEXT,
    recruiter_url   TEXT,
    discovered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status          TEXT DEFAULT 'discovered'
);
CREATE INDEX IF NOT EXISTS idx_discovered_status ON discovered_jobs(status);
CREATE INDEX IF NOT EXISTS idx_discovered_score ON discovered_jobs(score DESC);

-- Action queue (pending/approved/executed)
CREATE TABLE IF NOT EXISTS action_queue (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id              TEXT REFERENCES discovered_jobs(job_id),
    action_type         TEXT NOT NULL,       -- apply_easy/apply_external/connect/message
    status              TEXT DEFAULT 'pending_review',
    priority            INTEGER DEFAULT 0,
    content_draft       TEXT,                -- generated message/letter
    content_final       TEXT,                -- final version after edit
    target_profile_url  TEXT,                -- for connections/messages
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at         TIMESTAMP,
    result              TEXT,                -- success/failure + details
    error_message       TEXT
);
CREATE INDEX IF NOT EXISTS idx_queue_status ON action_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_job ON action_queue(job_id);

-- Company cache (TTL ~30 days)
CREATE TABLE IF NOT EXISTS companies (
    company_id      TEXT PRIMARY KEY,
    name            TEXT,
    industry        TEXT,
    size            TEXT,
    tech_stack      TEXT,                    -- JSON array
    last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recruiter cache (persists across sessions)
CREATE TABLE IF NOT EXISTS recruiters (
    recruiter_id    TEXT PRIMARY KEY,
    name            TEXT,
    company         TEXT,
    linkedin_url    TEXT,
    title           TEXT,
    last_contact    TIMESTAMP
);

-- Connections sent (limit tracking)
CREATE TABLE IF NOT EXISTS connections_sent (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id    TEXT,
    job_id          TEXT,
    note            TEXT,
    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status          TEXT                     -- sent/accepted/ignored
);
CREATE INDEX IF NOT EXISTS idx_connections_sent_at ON connections_sent(sent_at);

-- Pipeline run history
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP,
    status          TEXT,                    -- running/completed/failed/cancelled
    jobs_fetched    INTEGER DEFAULT 0,
    jobs_filtered   INTEGER DEFAULT 0,
    jobs_scored     INTEGER DEFAULT 0,
    jobs_queued     INTEGER DEFAULT 0,
    config          TEXT                     -- JSON: criteria used
);

-- Pipeline items (for resume capability)
CREATE TABLE IF NOT EXISTS pipeline_items (
    run_id          TEXT,
    job_id          TEXT,
    stage_completed TEXT,                    -- fetched/filtered/scored/generated
    score           REAL,
    PRIMARY KEY (run_id, job_id)
);

-- LLM response cache (content-hash based, TTL 7-14 days)
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key       TEXT PRIMARY KEY,        -- sha256(model + prompt)
    response        TEXT,
    model           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Execution log (audit trail)
CREATE TABLE IF NOT EXISTS execution_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id       INTEGER REFERENCES action_queue(id),
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event           TEXT,
    details         TEXT
);
CREATE INDEX IF NOT EXISTS idx_execution_log_action ON execution_log(action_id);
