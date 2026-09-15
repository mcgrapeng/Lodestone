"""PostgreSQL store — asyncpg-based query API for repos / history / plugins / notifications."""
from __future__ import annotations
import json
from typing import Any
import asyncpg

NOTIFY_KIND_NEW_REPO = "new_repo"
NOTIFY_KIND_MILESTONE = "milestone"
NOTIFY_KIND_SCORED = "scored"
NOTIFY_KIND_SYSTEM = "system"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS repos (
    name TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    description TEXT,
    stars INTEGER NOT NULL DEFAULT 0,
    forks INTEGER NOT NULL DEFAULT 0,
    lang TEXT,
    topics JSONB,
    best_category TEXT,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_crawled_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_repos_stars ON repos(stars DESC);
CREATE INDEX IF NOT EXISTS idx_repos_category ON repos(best_category);
CREATE INDEX IF NOT EXISTS idx_repos_last_seen ON repos(last_seen_at DESC);

CREATE TABLE IF NOT EXISTS repo_sources (
    repo_name TEXT NOT NULL REFERENCES repos(name) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    source_meta JSONB,
    PRIMARY KEY (repo_name, source_name)
);
CREATE INDEX IF NOT EXISTS idx_repo_sources_source ON repo_sources(source_name);

CREATE TABLE IF NOT EXISTS repo_categories (
    repo_name TEXT NOT NULL REFERENCES repos(name) ON DELETE CASCADE,
    category_id TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (repo_name, category_id)
);
CREATE INDEX IF NOT EXISTS idx_repo_categories_cat ON repo_categories(category_id);

CREATE TABLE IF NOT EXISTS stars_history (
    repo_name TEXT NOT NULL REFERENCES repos(name) ON DELETE CASCADE,
    snapshot_at TIMESTAMPTZ NOT NULL,
    stars INTEGER NOT NULL,
    PRIMARY KEY (repo_name, snapshot_at)
);
CREATE INDEX IF NOT EXISTS idx_stars_history_recent ON stars_history(snapshot_at DESC, repo_name);

CREATE TABLE IF NOT EXISTS crawl_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    source_name TEXT,
    repos_added INTEGER DEFAULT 0,
    repos_updated INTEGER DEFAULT 0,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_crawl_log_recent ON crawl_log(started_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    kind TEXT NOT NULL,
    repo_name TEXT,
    title TEXT NOT NULL,
    body TEXT,
    severity TEXT NOT NULL DEFAULT 'info'
);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(read_at, created_at DESC);

CREATE TABLE IF NOT EXISTS plugin_state (
    plugin_name TEXT NOT NULL,
    key TEXT NOT NULL,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (plugin_name, key)
);

CREATE TABLE IF NOT EXISTS plugin_manifest (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    version TEXT,
    config_schema JSONB,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    discovered_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""


class Store:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def ensure_schema(self) -> None:
        await self.conn.execute(SCHEMA_SQL)

    async def upsert_repo(self, repo, source_name: str) -> bool:
        is_new = await self.conn.fetchval("""
            INSERT INTO repos (name, url, description, stars, forks, lang, topics, last_crawled_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, NOW())
            ON CONFLICT (name) DO UPDATE SET
                url = EXCLUDED.url, description = EXCLUDED.description,
                stars = EXCLUDED.stars, forks = EXCLUDED.forks,
                lang = EXCLUDED.lang, topics = EXCLUDED.topics,
                last_crawled_at = NOW(), last_seen_at = NOW()
            RETURNING (xmax = 0) AS inserted
        """, repo.name, repo.url, repo.description, repo.stars, repo.forks,
             repo.lang, json.dumps(repo.topics))
        await self.conn.execute("""
            INSERT INTO repo_sources (repo_name, source_name, source_meta)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (repo_name, source_name) DO UPDATE SET
                source_meta = EXCLUDED.source_meta
        """, repo.name, source_name, json.dumps(repo.source_meta))
        return bool(is_new)

    async def upsert_stars_history(self, name: str, stars: int) -> None:
        await self.conn.execute("""
            INSERT INTO stars_history (repo_name, snapshot_at, stars)
            VALUES ($1, NOW(), $2)
            ON CONFLICT (repo_name, snapshot_at) DO UPDATE SET stars = EXCLUDED.stars
        """, name, stars)

    async def list_repos(self, filters: dict) -> list[dict]:
        where, params = [], []
        if filters.get("q"):
            params.append(f"%{filters['q']}%")
            where.append(f"(name ILIKE ${len(params)} OR description ILIKE ${len(params)})")
        if filters.get("category"):
            params.append(filters["category"])
            where.append(f"best_category = ${len(params)}")
        if filters.get("source"):
            params.append(filters["source"])
            where.append(f"name IN (SELECT repo_name FROM repo_sources WHERE source_name = ${len(params)})")
        sql = "SELECT name, url, description, stars, forks, lang, topics, best_category, last_seen_at FROM repos"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY stars DESC LIMIT " + str(int(filters.get("limit", 50)))
        rows = await self.conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def get_repo(self, name: str) -> dict | None:
        row = await self.conn.fetchrow("SELECT * FROM repos WHERE name = $1", name)
        return dict(row) if row else None

    async def set_plugin_state(self, plugin: str, key: str, value: Any) -> None:
        await self.conn.execute("""
            INSERT INTO plugin_state (plugin_name, key, value)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (plugin_name, key) DO UPDATE SET
                value = EXCLUDED.value, updated_at = NOW()
        """, plugin, key, json.dumps(value))

    async def get_plugin_state(self, plugin: str, key: str) -> Any | None:
        row = await self.conn.fetchrow(
            "SELECT value FROM plugin_state WHERE plugin_name = $1 AND key = $2", plugin, key)
        return json.loads(row["value"]) if row else None

    async def set_setting(self, key: str, value: Any) -> None:
        await self.conn.execute("""
            INSERT INTO settings (key, value) VALUES ($1, $2::jsonb)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """, key, json.dumps(value))

    async def get_setting(self, key: str) -> Any | None:
        row = await self.conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        return json.loads(row["value"]) if row else None

    async def insert_notification(self, n: dict) -> int:
        row = await self.conn.fetchrow("""
            INSERT INTO notifications (kind, title, body, repo_name, severity)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, n["kind"], n["title"], n.get("body", ""), n.get("repo_name"), n.get("severity", "info"))
        return int(row["id"])

    async def list_notifications(self, unread_only: bool, since) -> list[dict]:
        sql = "SELECT * FROM notifications"
        conds = []
        if unread_only:
            conds.append("read_at IS NULL")
        if since is not None:
            conds.append(f"created_at >= ${len(conds)+1}")
            rows = await self.conn.fetch(sql + " WHERE " + " AND ".join(conds) + " ORDER BY created_at DESC LIMIT 200", since)
        else:
            rows = await self.conn.fetch(sql + (" WHERE " + " AND ".join(conds) if conds else "") + " ORDER BY created_at DESC LIMIT 200")
        return [dict(r) for r in rows]

    async def mark_notification_read(self, nid: int) -> None:
        await self.conn.execute(
            "UPDATE notifications SET read_at = NOW() WHERE id = $1 AND read_at IS NULL", nid)

    async def upsert_plugin_manifest(self, name: str, kind: str, version: str, schema: dict, enabled: bool) -> None:
        await self.conn.execute("""
            INSERT INTO plugin_manifest (name, kind, version, config_schema, enabled)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            ON CONFLICT (name) DO UPDATE SET
                kind = EXCLUDED.kind, version = EXCLUDED.version,
                config_schema = EXCLUDED.config_schema, enabled = EXCLUDED.enabled,
                discovered_at = NOW()
        """, name, kind, version, json.dumps(schema), enabled)

    async def list_plugin_manifests(self) -> list[dict]:
        rows = await self.conn.fetch("SELECT * FROM plugin_manifest ORDER BY kind, name")
        return [dict(r) for r in rows]
