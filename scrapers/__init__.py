# -*- coding: utf-8 -*-
"""lodestone scraper tier — real-browser HTML fetchers for pages urllib can't render.

Adapters ported from youzi skill (firecrawl / crawl4ai / playwright), trimmed to
html-only: lodestone needs exactly one JS page (github.com/trending) reliably scraped.

Two orchestration modes:

  - `fetch_html(url, timeout, strategy="serial")` — serial fallback. First engine
    returning non-empty HTML wins; later engines are skipped. Cheap; predictable;
    used by tests + callers that need strict fallback semantics.

  - `fetch_html(url, strategy="parallel")` / `fetch_html_parallel(url, timeout)` —
    every available engine runs concurrently under one wall-clock deadline; the
    longest meaningful HTML wins (tie-break by engine priority). Engines race so
    fast ones short-circuit when good enough and slow ones enrich when needed.
    This is the "并行工作、相辅相成" mode — adapters complement each other instead
    of stopping at the first success.

The whole package is optional: zero deps installed → urllib still works in
`radar.fetch_github_trending` (which calls into this module).

Each adapter exposes:
  - `is_available() -> bool`
  - `scrape(url, timeout_seconds) -> dict` (sync, asyncio.run wrapper — for CLI)
  - `_async_scrape(url, timeout_seconds) -> dict` (async-safe core for parallel mode)
"""

import asyncio
import inspect
import sys

_ENGINE_ORDER = (
    "firecrawl",
    "crawl4ai",
    "playwright",
    "playwright_stealth",
    "cloudscraper",
    "httpx",
    "trafilatura",
    "beautifulsoup",
)
_PRIORITY = {name: i for i, name in enumerate(_ENGINE_ORDER)}


def _load(name: str):
    """Import a scraper module by name; return None on any failure.
    A broken optional dependency must never crash the orchestrator."""
    try:
        return __import__(
            f"scrapers.{name}_scraper",
            fromlist=["scrape", "is_available", "_async_scrape"],
        )
    except Exception as e:
        print(f"  [scrape] engine {name} unusable: {e}", file=sys.stderr)
        return None


def _engines():
    """Lazily yield (name, sync_scrape_fn) for every installed engine."""
    for name in _ENGINE_ORDER:
        mod = _load(name)
        if mod and mod.is_available():
            yield name, mod.scrape


def _async_engines():
    """Lazily yield (name, fn, is_async) for every installed engine.
    Uses `_async_scrape` ONLY when it's a real async function. Falls back to the
    sync `scrape` (wrapped by orchestrator in asyncio.to_thread) otherwise.
    ponytail: getattr() on a MagicMock-with-no-_async_scrape returns a child MagicMock
    (truthy); without the iscoroutinefunction gate, `MagicMock or mod.scrape` returns
    the MagicMock and we'd call asyncio.to_thread(MagicMock, ...) — which returns a
    MagicMock instead of a real result dict."""
    for name in _ENGINE_ORDER:
        mod = _load(name)
        if not (mod and mod.is_available()):
            continue
        async_fn = getattr(mod, "_async_scrape", None)
        if inspect.iscoroutinefunction(async_fn):
            yield name, async_fn, True
        else:
            yield name, mod.scrape, False


async def _scrape_one(name: str, fn, is_async: bool, url: str, timeout: int) -> dict:
    """Run one adapter; NEVER raise. Returns a clean dict with the standard shape.
    ponytail: we construct a fresh dict instead of mutating the adapter's result —
    prevents Mock/test-fixture auto-attribute magic from leaking 'MagicMock' into the
    `engine` field."""
    try:
        if is_async:
            r = await fn(url, timeout)
        else:
            r = await asyncio.to_thread(fn, url, timeout)
    except Exception as e:
        r = {"success": False, "html": "", "error": f"{type(e).__name__}: {e}"}
    if not isinstance(r, dict):
        r = {
            "success": False,
            "html": "",
            "error": f"non-dict result: {type(r).__name__}",
        }
    return {
        "scraper": name,
        "success": bool(r.get("success")),
        "html": r.get("html") or "",
        "error": r.get("error"),
    }


async def fetch_html_parallel_async(url: str, timeout: int = 60) -> tuple:
    """Run every available engine concurrently under one wall-clock deadline.
    Selection: longest non-empty HTML among those that finished in time;
    tie-break by engine priority (firecrawl < crawl4ai < playwright).
    Returns (html, engine_name); engine_name is "+"-joined list of contributors,
    or "none" when all engines failed."""
    engines = list(_async_engines())
    if not engines:
        return "", "none"
    tasks = [
        asyncio.create_task(_scrape_one(n, fn, is_a, url, timeout))
        for n, fn, is_a in engines
    ]
    # ponytail: asyncio.wait's two return sets are unused — we iterate `tasks` directly below
    # and check `t.done()` for completion. `asyncio.wait` is still required for the timeout
    # cancellation side-effect, which `asyncio.gather` does not provide.
    await asyncio.wait(tasks, timeout=timeout)
    # Cancel anything still running — don't leak subprocesses / browsers
    for t in tasks:
        if not t.done():
            t.cancel()
    # Drain cancellations so exceptions don't leak into GC warnings
    for t in tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass
    successes = [
        t.result()
        for t in tasks
        if t.done()
        and not t.cancelled()
        and t.result().get("success")
        and t.result().get("html")
    ]
    if successes:
        # ponytail: longest HTML wins; ties broken by engine priority. The result also
        # records every contributor so logs show "firecrawl+playwright" when both helped.
        successes.sort(key=lambda r: (-len(r["html"]), _PRIORITY.get(r["scraper"], 99)))
        contributors = sorted(
            {r["scraper"] for r in successes}, key=lambda n: _PRIORITY.get(n, 99)
        )
        return successes[0]["html"], "+".join(contributors)
    # All failed — log first error and return empty
    first_err = next(
        (
            t.result().get("error")
            for t in tasks
            if t.done() and not t.cancelled() and t.result().get("error")
        ),
        None,
    )
    if first_err:
        print(f"  [scrape] all engines failed: {first_err[:120]}", file=sys.stderr)
    return "", "none"


def fetch_html_parallel(url: str, timeout: int = 60) -> tuple:
    """Sync entry to parallel orchestration. `asyncio.run` here is the ONLY top-level loop —
    adapter cores never spawn their own, so there's no nested-loop crash."""
    return asyncio.run(fetch_html_parallel_async(url, timeout))


def fetch_html(
    url: str, timeout: int = 90, strategy: str = "parallel"
) -> tuple[str, str]:
    """Try each available engine in priority order.
    `strategy='serial'` — first non-empty HTML wins; later engines skipped.
    `strategy='parallel'` — every available engine runs concurrently; longest HTML wins.
    Returns (html, engine_name); ("", "none") when all fail."""
    if strategy == "parallel":
        return fetch_html_parallel(url, timeout=min(timeout, 90))
    for name, fn in _engines():
        try:
            r = fn(url, timeout=timeout)
        except Exception as e:
            print(f"  [scrape] {name} raised: {e}", file=sys.stderr)
            continue
        if r.get("success") and r.get("html"):
            return r["html"], name
        if r.get("error"):
            print(f"  [scrape] {name} failed: {str(r['error'])[:120]}", file=sys.stderr)
    return "", "none"


def status() -> dict:
    """{engine: available} map — printed at crawl start for observability."""
    out = {name: False for name in _ENGINE_ORDER}
    for name in _ENGINE_ORDER:
        mod = _load(name)
        out[name] = bool(mod and mod.is_available())
    return out
