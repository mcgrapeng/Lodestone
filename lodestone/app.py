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

    return app


app = create_app()
