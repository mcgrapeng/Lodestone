"""Crawl scheduler — cron-based async loop using croniter."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Awaitable, Callable

from croniter import croniter

log = logging.getLogger(__name__)
Action = Callable[[], Awaitable[None]]


class Scheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def add_cron(self, name: str, expr: str, action: Action) -> None:
        croniter(expr, datetime.now())  # validate
        self._jobs[name] = {"expr": expr, "action": action, "last_run": None}

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="lodestone-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None

    async def _loop(self) -> None:
        log.info("scheduler started with %d jobs", len(self._jobs))
        while not self._stop.is_set():
            now = datetime.now()
            for name, job in list(self._jobs.items()):
                itr = croniter(job["expr"], job["last_run"] or now)
                next_run = itr.get_next(datetime)
                if next_run <= now and (job["last_run"] is None or job["last_run"] < next_run):
                    job["last_run"] = now
                    try:
                        await job["action"]()
                    except Exception:
                        log.exception("scheduled job %s failed", name)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass
        log.info("scheduler stopped")

    async def run_now(self, name: str) -> None:
        if name not in self._jobs:
            raise KeyError(f"no such job: {name}")
        await self._jobs[name]["action"]()


scheduler = Scheduler()
