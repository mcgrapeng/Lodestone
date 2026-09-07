-- Lodestone: Postgres schema. Idempotent — safe to re-apply.

CREATE TABLE IF NOT EXISTS repos (
  name            TEXT PRIMARY KEY,                       -- 'owner/repo'
  full_name       TEXT NOT NULL,
  url             TEXT NOT NULL,
  description     TEXT,
  desc_zh         TEXT,
  stars           INT  NOT NULL DEFAULT 0,
  forks           INT  NOT NULL DEFAULT 0,
  lang            TEXT,
  topics          TEXT[] NOT NULL DEFAULT '{}',
  best_category   TEXT,                                   -- primary category id, NULL for top_5k+ only
  pushed_at       DATE,
  updated_at      DATE,
  is_ai_relevant  BOOLEAN NOT NULL DEFAULT FALSE,
  trending       BOOLEAN NOT NULL DEFAULT FALSE,           -- true iff repo appears on github.com/trending today
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_repos_stars  ON repos(stars DESC)   WHERE is_ai_relevant;
CREATE INDEX IF NOT EXISTS idx_repos_pushed ON repos(pushed_at DESC) WHERE is_ai_relevant;
CREATE INDEX IF NOT EXISTS idx_repos_topics ON repos USING GIN(topics);

-- ponytail: incremental schema migrations — ALTER is idempotent so re-running ensure_schema() is safe.
ALTER TABLE repos ADD COLUMN IF NOT EXISTS trending BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE repos ADD COLUMN IF NOT EXISTS stars_today INT;  -- github.com/trending scrape: stars gained in last 24h
CREATE INDEX IF NOT EXISTS idx_repos_trending ON repos(trending) WHERE trending;
CREATE INDEX IF NOT EXISTS idx_repos_stars_today ON repos(stars_today DESC) WHERE stars_today IS NOT NULL;

-- ponytail: 2026-08 — comprehensive Chinese descriptions + traceability.
-- readme_zh = translated README first paragraphs; readme_zh_source = provenance
-- (GitHub raw URL + fetch timestamp + translator); readme_zh_at = last translation time.
ALTER TABLE repos ADD COLUMN IF NOT EXISTS readme_zh TEXT;
ALTER TABLE repos ADD COLUMN IF NOT EXISTS readme_zh_source TEXT;
ALTER TABLE repos ADD COLUMN IF NOT EXISTS readme_zh_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS repo_categories (
  repo_name    TEXT NOT NULL REFERENCES repos(name) ON DELETE CASCADE,
  category_id  TEXT NOT NULL,
  PRIMARY KEY (repo_name, category_id)
);

-- ponytail: append-only stars snapshot — one row per (repo, crawl)
CREATE TABLE IF NOT EXISTS repo_stars_history (
  repo_name    TEXT NOT NULL REFERENCES repos(name) ON DELETE CASCADE,
  snapshot_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  stars        INT  NOT NULL,
  PRIMARY KEY (repo_name, snapshot_at)
);
CREATE INDEX IF NOT EXISTS idx_stars_history_recent
  ON repo_stars_history(snapshot_at DESC, repo_name);

CREATE TABLE IF NOT EXISTS crawl_log (
  id            SERIAL PRIMARY KEY,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at   TIMESTAMPTZ,
  repos_seen    INT,
  repos_added   INT,
  repos_updated INT,
  queries_failed INT DEFAULT 0    -- GitHub queries that errored/timed out this run (data-quality signal)
);

ALTER TABLE crawl_log ADD COLUMN IF NOT EXISTS queries_failed INT DEFAULT 0;
