"""Lodestone 2.0 — FastAPI app entry point."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI

from lodestone import __version__


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Lodestone", version=__version__, lifespan=_lifespan)

    @app.get("/api/health")
    async def health():
        return {"ok": True, "version": __version__, "plugins": 0}

    return app


app = create_app()
