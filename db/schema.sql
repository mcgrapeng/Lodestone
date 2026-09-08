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

-- ponytail: 2026-09 — SKILL.md 探测 + 结构化中文摘要。
-- is_skill = 仓库根或子目录含 SKILL.md / skill.md / SKILL.yaml（前端据此门控安装）。
-- summary_sections_json = {intro, can_do, benefit} 三桶中文摘要（README 段落拆分翻译）。
-- analysis_5d_json = LLM 5 维度决策分析 {what, problem, alternatives, pros, cons,
-- when_to_use}。NULL 表示未调 LLM（无 key / 超阈值）；前端降级到 summary_sections。
ALTER TABLE repos ADD COLUMN IF NOT EXISTS is_skill BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE repos ADD COLUMN IF NOT EXISTS summary_sections_json JSONB;
ALTER TABLE repos ADD COLUMN IF NOT EXISTS analysis_5d_json JSONB;

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

-- ─────────────────────────────────────────
-- 2026-09 数据修复迁移(幂等;ensure_schema 每次 crawl 前重放,无重复时零效果)

-- P2:合并大小写变体行 — GitHub 仓库改名/大小写归一后,同一仓库会出现
-- owner/Repo 与 owner/repo 两行(应用层合并键已统一小写,此处清历史存量)。
-- 每组保留 stars 最大(平星标比 last_seen_at,再比 name 保证确定性);
-- 子表行随 ON DELETE CASCADE 级联删除,分类关联下次 crawl 重建。
DELETE FROM repos a
USING repos b
WHERE a.name <> b.name
  AND lower(a.name) = lower(b.name)
  AND (a.stars, a.last_seen_at, a.name) < (b.stars, b.last_seen_at, b.name);

-- P3:stars 快照按天去重 — (repo, snapshot_at) 秒级主键使同日多次 crawl 产生
-- 多行;先保每天最新一行,再把 snapshot_at 归一到当天零点(query_gain 语义不变)。
DELETE FROM repo_stars_history a
USING repo_stars_history b
WHERE a.repo_name = b.repo_name
  AND date_trunc('day', a.snapshot_at) = date_trunc('day', b.snapshot_at)
  AND a.snapshot_at < b.snapshot_at;
UPDATE repo_stars_history
SET snapshot_at = date_trunc('day', snapshot_at)
WHERE snapshot_at <> date_trunc('day', snapshot_at);
