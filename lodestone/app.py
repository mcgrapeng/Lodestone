"""Lodestone 2.0 — FastAPI app with plugin registry + scheduler + bus wiring."""
from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from fastapi import FastAPI, HTTPException, Query

from lodestone import __version__
from lodestone.bus import bus
from lodestone.registry import registry
from lodestone.scheduler import scheduler
from lodestone.store import Store

log = logging.getLogger(__name__)


def _db_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/ai_radar")


async def _make_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(_db_url(), min_size=1, max_size=4)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    registry.discover()
    pool = None
    try:
        pool = await _make_pool()
    except Exception as e:
        log.warning("DB unavailable at startup: %s", e)
    app.state.pool = pool
    if pool:
        async with pool.acquire() as conn:
            store = Store(conn)
            await store.ensure_schema()
            for kind in ("source", "scorer", "notifier"):
                for name, cls in registry.list_by_kind(kind):
                    await store.upsert_plugin_manifest(
                        name=name, kind=kind, version=getattr(cls, "version", "0"),
                        schema=getattr(cls, "config_schema", {}), enabled=True)
            inapp = registry.get("in_app")
            if inapp is not None and hasattr(inapp, "bind_store"):
                inapp.bind_store(store)
    async def _on_source_crawled(payload):
        repo, source_name = payload
        for name, _ in registry.list_by_kind("scorer"):
            scorer = registry.get(name)
            if scorer is None: continue
            try:
                await scorer.score({"name": repo.name, "stars": repo.stars}, {})
            except Exception:
                log.exception("scorer %s failed", name)
        for name, _ in registry.list_by_kind("notifier"):
            notifier = registry.get(name)
            if notifier is None: continue
            try:
                await notifier.notify({
                    "kind": "new_repo", "title": f"New: {repo.name}",
                    "body": repo.description or "", "repo_name": repo.name,
                    "severity": "info"})
            except Exception:
                log.exception("notifier %s failed", name)
    bus.subscribe("source.crawled", _on_source_crawled)
    # ponytail: only start scheduler when DB is available — keeps lifespan
    # event-loop-clean for TestClient (which runs lifespan + requests in
    # separate loops; the scheduler's Event/Task otherwise leaks across).
    if pool is not None:
        await scheduler.start()
    try:
        yield
    finally:
        if pool is not None:
            await scheduler.stop()
            await pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Lodestone", version=__version__, lifespan=_lifespan)

    @app.get("/api/health")
    async def health():
        return {"ok": True, "version": __version__, "plugins": len(registry._plugins)}

    @app.get("/api/repos")
    async def list_repos(q: str | None = None, category: str | None = None,
                          source: str | None = None, limit: int = Query(50, le=200)):
        if app.state.pool is None:
            raise HTTPException(503, "db unavailable")
        filters = {"limit": limit}
        if q: filters["q"] = q
        if category: filters["category"] = category
        if source: filters["source"] = source
        async with app.state.pool.acquire() as conn:
            return await Store(conn).list_repos(filters)

    @app.get("/api/repos/{name}")
    async def get_repo(name: str):
        if app.state.pool is None:
            raise HTTPException(503, "db unavailable")
        async with app.state.pool.acquire() as conn:
            r = await Store(conn).get_repo(name)
            if r is None:
                raise HTTPException(404, f"repo not found: {name}")
            return r

    @app.get("/api/sources")
    async def list_sources():
        return [
            {"name": n, "kind": k, "version": getattr(c, "version", "0"),
             "config_schema": getattr(c, "config_schema", {})}
            for k in ("source", "scorer", "notifier")
            for n, c in registry.list_by_kind(k)
        ]

    @app.get("/api/sources/{name}")
    async def get_source(name: str):
        for k in ("source", "scorer", "notifier"):
            for n, c in registry.list_by_kind(k):
                if n == name:
                    return {"name": n, "kind": k, "version": getattr(c, "version", "0"),
                            "config_schema": getattr(c, "config_schema", {})}
        raise HTTPException(404, f"plugin not found: {name}")

    # ---- 7 write endpoints ----

    from pydantic import BaseModel
    from datetime import datetime, timezone

    class _ConfigBody(BaseModel):
        config: dict = {}

    @app.post("/api/sources/{name}/config")
    async def set_source_config(name: str, body: _ConfigBody):
        if app.state.pool is None:
            raise HTTPException(503, "db unavailable")
        async with app.state.pool.acquire() as conn:
            store = Store(conn)
            for k, v in body.config.items():
                await store.set_plugin_state(name, k, v)
        return {"ok": True}

    @app.post("/api/sources/{name}/test")
    async def test_source(name: str):
        plugin = registry.get(name)
        if plugin is None:
            raise HTTPException(404, f"plugin not found: {name}")
        count = 0
        try:
            async for _ in plugin.crawl():
                count += 1
                if count >= 5:
                    break
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "sampled": count}

    @app.post("/api/crawl")
    async def trigger_crawl(source: str | None = None):
        if source:
            try:
                await scheduler.run_now(source)
            except KeyError as e:
                raise HTTPException(404, str(e))
        else:
            for name, _ in registry.list_by_kind("source"):
                try:
                    await scheduler.run_now(name)
                except Exception as e:
                    log.warning("crawl %s failed: %s", name, e)
        return {"ok": True, "triggered": source or "all"}

    @app.get("/api/notifications")
    async def list_notifications(unread_only: bool = False, since: str | None = None):
        if app.state.pool is None:
            raise HTTPException(503, "db unavailable")
        since_dt = datetime.fromisoformat(since) if since else None
        async with app.state.pool.acquire() as conn:
            return await Store(conn).list_notifications(unread_only=unread_only, since=since_dt)

    @app.post("/api/notifications/{nid}/read")
    async def mark_read(nid: int):
        if app.state.pool is None:
            raise HTTPException(503, "db unavailable")
        async with app.state.pool.acquire() as conn:
            await Store(conn).mark_notification_read(nid)
        return {"ok": True}

    @app.get("/api/settings")
    async def get_llm_settings():
        from pathlib import Path
        import json
        p = Path("data/settings.json")
        if p.exists():
            return json.loads(p.read_text())
        return None

    @app.post("/api/settings")
    async def save_llm_settings(body: dict):
        from pathlib import Path
        import json
        p = Path("data/settings.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2))
        tmp.replace(p)
        return {"ok": True}

    # ---- 1.x compatibility: GET /api/data ----
    @app.get("/api/data")
    async def get_data():
        if app.state.pool is None:
            raise HTTPException(503, "db unavailable")
        async with app.state.pool.acquire() as conn:
            store = Store(conn)
            hot = await store.list_repos({"limit": 60})
            cats_rows = await store.conn.fetch("""
                SELECT category_id, COUNT(*) AS count
                FROM repo_categories
                GROUP BY category_id
            """)
            return {
                "hot_now": hot,
                "categories": [{"id": r["category_id"], "count": r["count"]} for r in cats_rows],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

    # ---- enrichment state (5-bucket host-LLM pass) ----
    from lodestone import enrich

    @app.get("/api/enrich/status")
    async def enrich_status():
        return {
            "enriched": enrich.is_enriched(),
            "at": enrich.enriched_at(),
        }

    @app.post("/api/enrich/reset")
    async def enrich_reset():
        enrich.clear()
        return {"ok": True}

    @app.post("/api/enrich/mark")
    async def enrich_mark():
        """Host LLM calls this after a successful 5-bucket enrichment pass.

        Sets data/.enriched_at to the current UTC timestamp. Subsequent
        /yz:ai calls will see enriched=true and skip auto-enrichment.
        """
        ts = enrich.mark_enriched()
        return {"ok": True, "at": ts}

    return app


app = create_app()
