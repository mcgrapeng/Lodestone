# Lodestone: Postgres Migration + Daily Star Gain

> **Spec for:** moving data layer from `data/latest.json` to local Postgres + adding a daily star-gain section.
> **Date:** 2026-07-20.

---

## 1. Goal

Move the hot_now / top_5k+ / categories storage from `data/latest.json` to a local PostgreSQL database. Add a new dashboard section that shows the **top 30 AI projects by 24-hour star gain**. Drop X/Twitter signal (no API token). PG is the **only** source of truth for repo data going forward.

## 2. Architecture

```
┌────────────────────────────────────────────────────────────┐
│ radar.py                                                    │
│  ├── db.py          ← new: psycopg-free pg8000 client      │
│  ├── crawl()        ← writes to PG via upsert              │
│  └── serve          ← reads from PG for all /api/* routes  │
└────────────────────────────────────────────────────────────┘
                ↓                           ↑
        write (UPSERT)                read (SELECT)
                ↓                           ↑
        ┌───────────────────────────────────────┐
        │  PostgreSQL @ 127.0.0.1:5432           │
        │  database: ai_radar                     │
        │  tables: repos, repo_categories,       │
        │          repo_stars_history,           │
        │          crawl_log                     │
        └───────────────────────────────────────┘
```

## 3. Why pg8000

Pure Python, no native libpq dependency, works on any Python including 3.14. The project was stdlib-only so far — pg8000 minimizes the footprint (one import) vs. psycopg2/3 which need C-extension builds that often fail on cutting-edge Python.

If a future use case demands 10× the throughput, swap to psycopg3 (one import line).

## 3.5 Connection

- Docker container ID `3195bfdcff80dad30c7b17eafe8453bb50945f620f792aa9cd38de118306e30c` (name `innies-postgres`, image `postgres:17-alpine`)
- Host port `5432`, user `postgres`, password `zpeng512`, default DB `postgres`
- New database `ai_radar` created on first connect (idempotent CREATE DATABASE)
- Connection string sourced from env: `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` (with hardcoded defaults matching the docker container above)

## 4. Schema (`db/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS repos (
  name            TEXT PRIMARY KEY,            -- 'owner/repo'
  full_name       TEXT NOT NULL,
  url             TEXT NOT NULL,
  description     TEXT,
  desc_zh         TEXT,
  stars           INT  NOT NULL DEFAULT 0,
  forks           INT  NOT NULL DEFAULT 0,
  lang            TEXT,
  topics          TEXT[] NOT NULL DEFAULT '{}',
  best_category   TEXT,                       -- NULL when in top_5k+ only
  pushed_at       DATE,
  updated_at      DATE,
  is_ai_relevant  BOOLEAN NOT NULL DEFAULT FALSE,
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_repos_stars  ON repos(stars DESC)  WHERE is_ai_relevant;
CREATE INDEX IF NOT EXISTS idx_repos_pushed ON repos(pushed_at DESC) WHERE is_ai_relevant;
CREATE INDEX IF NOT EXISTS idx_repos_topics ON repos USING GIN(topics);

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
  repos_updated INT
);
```

## 5. Upsert semantics

Per crawl:
```
BEGIN;
  INSERT INTO repos (...) VALUES (...)
    ON CONFLICT (name) DO UPDATE SET
      stars         = EXCLUDED.stars,
      forks         = EXCLUDED.forks,
      lang          = EXCLUDED.lang,
      topics        = EXCLUDED.topics,
      pushed_at     = EXCLUDED.pushed_at,
      updated_at    = EXCLUDED.updated_at,
      description   = EXCLUDED.description,
      desc_zh       = EXCLUDED.desc_zh,
      is_ai_relevant = EXCLUDED.is_ai_relevant,
      last_seen_at  = NOW();
  DELETE FROM repo_categories WHERE repo_name IN (...seen names);
  INSERT INTO repo_categories VALUES ...;
  INSERT INTO repo_stars_history (repo_name, stars)
    SELECT name, stars FROM repos WHERE name IN (...seen names);
COMMIT;
```

- **Mutable fields** (overwritten each crawl): `stars`, `forks`, `lang`, `topics`, `pushed_at`, `updated_at`, `description`, `desc_zh`, `is_ai_relevant`, `last_seen_at`.
- **Immutable fields** (set once on insert): `name`, `full_name`, `url`, `first_seen_at`.
- `repo_categories` re-replaced each crawl (a repo may move categories).
- A fresh `repo_stars_history` row is appended **every crawl**.

## 6. API endpoints

| Path | Source | Notes |
|------|--------|-------|
| `GET /api/data` | PG | `categories` + `hot_now` shape unchanged, just queried |
| `GET /api/top?page&size&sort` | PG | Same params, reads from `repos WHERE is_ai_relevant AND best_category IS NULL` |
| **`GET /api/gain?limit=30`** | PG | **NEW** — top-N by 24h star delta |
| `GET /api/local` | filesystem | unchanged |
| `POST /api/install` etc. | filesystem + sidecar | unchanged |

### `/api/gain` query

```sql
WITH prev AS (
  SELECT DISTINCT ON (repo_name) repo_name, stars AS stars_prev
  FROM repo_stars_history
  WHERE snapshot_at <= NOW() - INTERVAL '20 hours'
  ORDER BY repo_name, snapshot_at DESC
),
now AS (
  SELECT DISTINCT ON (repo_name) repo_name, stars AS stars_now
  FROM repo_stars_history
  WHERE snapshot_at >= NOW() - INTERVAL '4 hours'
  ORDER BY repo_name, snapshot_at DESC
)
SELECT r.name, r.url, r.desc_zh, r.lang, r.stars,
       COALESCE(now.stars_now - prev.stars_prev, 0) AS delta_24h
FROM repos r
LEFT JOIN prev  ON prev.repo_name  = r.name
LEFT JOIN now   ON now.repo_name   = r.name
WHERE r.is_ai_relevant
ORDER BY delta_24h DESC, r.stars DESC
LIMIT $1;
```

**Cold start** (first crawl, no yesterday snapshot): `delta_24h = 0` for all rows. UI shows `stars × 0` row but it's harmless — by day 2 the gain signal becomes meaningful.

## 7. Crawl flow changes

Same 14 query sources (9 categories + 5 5k+ queries, same whitelist). Changes:
- All GitHub data normalized into repo dicts
- `crawl()` opens PG connection at start, ensures schema, runs ONE transaction
- `latest.json` writes **removed** (or kept as a debug snapshot, optional)
- Crawl log: insert into `crawl_log`

## 8. AI relevance filter (kept)

Existing `AI_TOPIC_WHITELIST` frozenset (45 topics) + new explicit blocklist:
```python
AI_TOPIC_BLOCKLIST = frozenset({
  "stock", "stocks", "trading", "crypto", "nft", "forex", "porn",
  "ai-porn", "ai-girlfriend", "adult-content",
  "astrology", "fortune-telling",
})
```
Filter rule: `is_ai_relevant = (any topic ∈ whitelist) AND (no topic ∈ blocklist)`.

## 9. Frontend changes

- **New button** in Hero right-side group: `🚀 今日星增`
- New route: `?page=gain` (mirrors `/top` pattern from Task 7)
- New view template section gated on `view === 'gain'`
- Cards show: name · ⭐ current · 🔥 +1,234 (24h)
- Sort + paginate via the new `/api/gain` endpoint (extend with page/size later if >30)

## 10. Tests

Add to `tests/test_radar.py`:
- `test_db_upsert_inserts_new_repo`
- `test_db_upsert_updates_mutates_only`
- `test_db_snapshot_appends_history_row`
- `test_api_gain_orders_by_delta_desc` (cold start → all delta=0)
- `test_api_gain_filters_non_ai_relevant`
- `test_blocklist_excludes_trading_repos`

## 11. Files to create/change

- **Create** `db/schema.sql`, `db/__init__.py`, `db/connection.py`, `db/repos.py` (upserts + queries)
- **Create** `tests/test_db.py` (runs against real local PG)
- **Modify** `radar.py`: drop `latest.json` writes, route `/api/data`, `/api/top`, new `/api/gain` through PG
- **Modify** `frontend/src/App.vue`: add `🚀 今日星增` button + `gain` view + CSS for `.gain-card`
- **Add** `requirements.txt` with `pg8000>=1.30`

## 12. Out of scope (explicit non-goals)

- No multi-tenant / multi-crawl-user support
- No auth on /api/* (still single-machine dashboard)
- No historical retention beyond N crawls (run a vacuum job later if needed)
- No replumbing of `data/latest.json` for `out/index.html` (static HTML render path stays broken — use Vite)
- X/Twitter — explicitly dropped per user decision

---

**Bottoms up; ready for plan + implementation.** Want me to spin up the implementation tasks now?
