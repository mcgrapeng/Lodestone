# -*- coding: utf-8 -*-
"""lodestone scraper tier — engine ladder for pages urllib can't fetch.

2026-09 精简：引擎 14 → 4，按"精、互补、开源、主流"选择，每级解决一种
别的级解决不了的失败模式：

    1. httpx             本地纯 HTTP        — 最快路径（trending 是 SSR，多数直接命中）
    2. cloudscraper      本地 HTTP + 挑战破解 — bot-check 中间页，无需浏览器
    3. playwright_stealth 本地真浏览器       — JS 渲染 / 严格指纹检测
    4. jina              云端渲染（换出口 IP）— 本地 IP 被封时逃生

其余 10 个适配器（firecrawl/crawl4ai/playwright/nodriver/crawlee/scrapy/
agent_reach/trafilatura/beautifulsoup/drissionpage）能力与上述 4 个重叠，
已从 config.toml priority 停用但代码保留 — priority 列表是唯一白名单。

三种编排模式（config.toml [orchestrator].selection_strategy，可被调用方
的 strategy= 参数覆盖）：

  - `tiered`（默认）— 分级 fallback：按 URL 分发顺序轻→重逐级尝试，
    每级结果过质量门（长度 + bot-check 特征 + 已知页面的结构标记），
    通过即返回；不过才升级更重的引擎。共享 wall-clock 预算。
  - `longest` — 全引擎并行竞赛，最长 HTML 胜出（旧行为，调试用）。
    strategy="parallel" 同义。
  - `first` — 首个非空结果胜出，不做质量检查。strategy="serial" 同义。

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
import time

from .config_loader import (
    get_min_html_length,
    get_priority,
    get_selection_strategy,
    get_timeout,
    get_wall_clock_timeout,
)

# ponytail: _ENGINE_ORDER is derived from config.toml (orchestrator.priority) and
# doubles as the ALLOWLIST — engines not listed there can never run, no matter
# what url_dispatcher suggests. Adapter code reads per-engine timeouts / UAs
# via config_loader — no hardcoded values.
_ENGINE_ORDER = tuple(get_priority())
_PRIORITY = {name: i for i, name in enumerate(_ENGINE_ORDER)}

# ponytail: URL-aware dispatch. select_engines(url) returns the ladder order for
# this URL family; quality_marker(url) returns the "real page" signature used
# by the tiered quality gate.
from .url_dispatcher import content_hint, quality_marker, select_engines  # noqa: E402

# ponytail: bot-check 中间页特征 — 命中任意一条即质量门不通过（升级下一级引擎）。
# 只查前 5000 字符：这类页面通常又短又靠前，避免大页面上的多余扫描。
_BOT_CHECK_MARKERS = (
    "just a moment",                  # Cloudflare challenge
    "checking your browser",          # Cloudflare legacy
    "attention required",             # Cloudflare block
    "enable javascript and cookies",  # generic bot wall
    "unusual traffic",                # Google-style block
    "sign in to your account",        # auth-wall served instead of content
)


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


def _engines(url: str = ""):
    """Lazily yield (name, sync_scrape_fn) for every enabled+installed engine.

    Order: url_dispatcher's family list when `url` is given, else the global
    priority. Engines missing from the config priority allowlist are skipped —
    a disabled engine must never be resurrected by a dispatcher rule."""
    order = select_engines(url) if url else _ENGINE_ORDER
    for name in order:
        if name not in _PRIORITY:
            continue
        mod = _load(name)
        if mod and mod.is_available():
            yield name, mod.scrape


def _async_engines(url: str = ""):
    """Lazily yield (name, fn, is_async) for every enabled+installed engine.
    Uses `_async_scrape` ONLY when it's a real async function. Falls back to the
    sync `scrape` (wrapped by orchestrator in asyncio.to_thread) otherwise.
    ponytail: getattr() on a MagicMock-with-no-_async_scrape returns a child MagicMock
    (truthy); without the iscoroutinefunction gate, `MagicMock or mod.scrape` returns
    the MagicMock and we'd call asyncio.to_thread(MagicMock, ...) — which returns
    a a MagicMock instead of a real result dict.

    Same allowlist rule as `_engines` — priority list is the single source of truth.
    """
    for name, fn in _engines(url):
        mod = _load(name)
        async_fn = getattr(mod, "_async_scrape", None)
        if inspect.iscoroutinefunction(async_fn):
            yield name, async_fn, True
        else:
            yield name, fn, False


def quality_ok(html: str, url: str = "") -> bool:
    """质量门 — 某级引擎拿到的是"真页面"吗？

    三层判据（全部通过才算过）：
      1. 长度 ≥ config.min_html_length（默认 500，bot-check 页普遍很短）
      2. 前 5000 字符不含 bot-check 特征
      3. 已知页面的结构标记足够多（如 trending 须有 ≥5 个 Box-row article），
         与 radar.py 的解析正则耦合 — 拿不到标记 = 解析器也解析不出东西
    """
    if not html or len(html) < get_min_html_length():
        return False
    head = html[:5000].lower()
    if any(marker in head for marker in _BOT_CHECK_MARKERS):
        return False
    structural = quality_marker(url)
    if structural is not None:
        needle, minimum = structural
        return html.count(needle) >= minimum
    return True


async def _scrape_one(name: str, fn, is_async: bool, url: str, timeout: int) -> dict:
    """Run one adapter; NEVER raise. Returns a clean dict with the standard shape.
    ponytail: we construct a fresh dict instead of mutating the adapter's result —
    prevents Mock/test-fixture auto-attribute magic from leaking 'MagicMock' into
    the `engine` field.

    `markdown` is preserved when the adapter returns it (jina / trafilatura /
    agent_reach). The orchestrator surfaces it via `content_hint(url) == "markdown"`.
    """
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
        "markdown": r.get("markdown") or "",
        "error": r.get("error"),
    }


async def fetch_html_parallel_async(url: str, timeout: int = 60) -> tuple:
    """Run every available engine concurrently under one wall-clock deadline.
    Selection: longest non-empty HTML among those that finished in time;
    tie-break by engine priority.
    Returns (html, engine_name); engine_name is "+"-joined list of contributors,
    or "none" when all engines failed.

    ponytail: parallel is no longer the default (2026-09) — it launches every
    engine including the Chromium ones on every call. Kept for strategy="longest"
    / debugging. Honors `content_hint(url)`: "markdown"-hinted URLs accept
    markdown returns even when shorter than the HTML competitor.
    """
    engines = list(_async_engines(url))
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
        # records every contributor so logs show "httpx+cloudscraper" when both helped.
        successes.sort(key=lambda r: (-len(r["html"]), _PRIORITY.get(r["scraper"], 99)))
        # content hint: for "markdown"-hinted URLs, prefer engines whose
        # `html` field actually IS markdown. Markdown is usually shorter than
        # full HTML, so the plain length-pick would lose it. We accept markdown
        # when its length ≥ 50% of the longest HTML alternative.
        hint = content_hint(url)
        if hint == "markdown":
            markdown_engines = {"jina", "trafilatura", "agent_reach"}
            md_winner = next(
                (r for r in successes if r["scraper"] in markdown_engines and len(r["html"]) >= 200),
                None,
            )
            if md_winner:
                top = successes[0]
                # use markdown only when it's at least half the HTML winner's size
                if len(md_winner["html"]) >= len(top["html"]) * 0.5:
                    contributors = sorted(
                        {r["scraper"] for r in successes if len(r["html"]) >= 200},
                        key=lambda n: _PRIORITY.get(n, 99),
                    )
                    return md_winner["html"], "+".join(contributors)
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


def fetch_html_tiered(
    url: str, timeout: int = 90, use_quality_gate: bool = True
) -> tuple[str, str]:
    """分级 fallback — 轻引擎先上，拿到真页面就停，否则逐级加重。

    每级共享一个 wall-clock 预算（min(timeout, config.wall_clock_timeout)），
    引擎自身的 timeout 取 min(配置值, 剩余预算)，预算耗尽不再升级。
    返回 (html, engine_name)；全部失败返回 ("", "none")。
    若所有引擎都返回了"未过质量门"的内容，回退返回最长的一个（调用方
    的解析器/搜索代理兜底），engine 名照实标注。
    """
    deadline = time.monotonic() + min(timeout, get_wall_clock_timeout())
    best_rejected: tuple[str, str] = ("", "none")
    tried: list[str] = []

    for name, fn in _engines(url):
        remaining = deadline - time.monotonic()
        if remaining <= 1.5:
            # 预算不足以再跑一级更重的引擎 — 直接停在当前最优
            print(
                f"  [scrape] tiered: wall-clock budget exhausted after "
                f"{'+'.join(tried) or 'no engine'}",
                file=sys.stderr,
            )
            break
        tried.append(name)
        # 引擎自身超时不得吃掉整段预算：取配置值与剩余预算的较小者
        t = min(get_timeout(name, default=60), int(remaining))
        try:
            r = fn(url, timeout=t)
        except Exception as e:
            print(f"  [scrape] {name} raised: {e}", file=sys.stderr)
            continue
        html = r.get("html") or ""
        passed = bool(r.get("success")) and html
        if passed and use_quality_gate:
            passed = quality_ok(html, url)
        if passed:
            print(
                f"  [scrape] {name} ✓ {len(html)} chars"
                f"{' (quality gate passed)' if use_quality_gate else ''}",
                file=sys.stderr,
            )
            return html, name
        if html and len(html) > len(best_rejected[0]):
            best_rejected = (html, name)
        why = (
            "quality gate: bot-check / unparseable page"
            if html
            else (r.get("error") or "empty")
        )
        print(f"  [scrape] {name} ✗ {str(why)[:100]} — escalating", file=sys.stderr)

    if best_rejected[0]:
        print(
            f"  [scrape] tiered: ladder exhausted ({'+'.join(tried)}); "
            f"best-effort from {best_rejected[1]}",
            file=sys.stderr,
        )
    elif tried:
        print(f"  [scrape] tiered: ladder exhausted ({'+'.join(tried)})", file=sys.stderr)
    return best_rejected


def fetch_html(
    url: str, timeout: int = 90, strategy: str | None = None
) -> tuple[str, str]:
    """Fetch one URL with the configured orchestration strategy.

    strategy=None → config.toml [orchestrator].selection_strategy（默认 tiered）。
    显式取值：
      "tiered"          分级 fallback + 质量门（推荐，radar.py 使用）
      "serial" / "first"  分级 fallback，不做质量检查（首个非空结果胜出）
      "parallel" / "longest"  全引擎并行竞赛，最长 HTML 胜出（调试用）
    Returns (html, engine_name); ("", "none") when all fail."""
    if strategy is None:
        strategy = get_selection_strategy()
    # 旧配置值映射：longest=并行竞赛 / first=无质量门的阶梯
    if strategy in ("parallel", "longest"):
        # parallel mode uses orchestrator.wall_clock_timeout from config.toml
        # (default 60s) — caller's `timeout` arg still acts as a per-call ceiling
        # that never exceeds the config value.
        cap = min(timeout, get_wall_clock_timeout())
        return fetch_html_parallel(url, timeout=cap)
    use_gate = strategy not in ("first", "serial")
    return fetch_html_tiered(url, timeout=timeout, use_quality_gate=use_gate)


def status() -> dict:
    """{engine: available} map — printed at crawl start for observability.
    Only covers engines enabled in config.toml priority (the allowlist)."""
    out = {}
    for name in _ENGINE_ORDER:
        mod = _load(name)
        out[name] = bool(mod and mod.is_available())
    return out
