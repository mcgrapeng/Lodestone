"""Tests for scrapers/ chain + trending HTML parse. Run: python3 -m tests.test_scrapers

2026-09：引擎 14 → 4（httpx / cloudscraper / playwright_stealth / jina），
默认编排 = tiered（分级 fallback + 质量门）。测试覆盖：
  - 分级升级：轻引擎过质量门即停；bot-check/空壳页升级下一级
  - 白名单：config priority 之外的引擎永不运行
  - 质量门三层判据（长度 / bot 特征 / 已知页面结构标记）
  - 并行模式（strategy="parallel"，调试用）的旧行为保持不变
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
import radar
import scrapers
from scrapers.url_dispatcher import quality_marker, select_engines


ALL_ENGINES = (
    "httpx", "cloudscraper", "playwright_stealth", "jina",          # 启用（priority 白名单）
    "firecrawl", "crawl4ai", "playwright", "nodriver", "crawlee",   # 停用但适配器保留
    "scrapy", "agent_reach", "trafilatura", "beautifulsoup", "drissionpage",
)
ACTIVE = {"httpx", "cloudscraper", "playwright_stealth", "jina"}


def _mock_engines(scrape_fns: dict, extra_available=()):
    """Build the full 14-module mock set.

    scrape_fns: {engine_name: scrape_fn} — these engines are available.
    extra_available: engine names available but WITHOUT a scrape fn listed
    (only meaningful for allowlist tests — they must never be called anyway).
    Every other engine is marked unavailable so the real installed adapters
    can't sneak in and change behavior under test.
    """
    mods = {}
    for name in ALL_ENGINES:
        if name in scrape_fns:
            mods[f"{name}_scraper"] = MagicMock(
                is_available=lambda: True, scrape=scrape_fns[name]
            )
        elif name in extra_available:
            mods[f"{name}_scraper"] = MagicMock(is_available=lambda: True)
        else:
            mods[f"{name}_scraper"] = MagicMock(is_available=lambda: False)
    return patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in mods.items()})


def _fn(html="", raises=False, error=None):
    """Sync scrape fn returning a fixed result."""
    def fn(url, timeout=90):
        if raises:
            raise RuntimeError(f"{html or 'engine'} boom")
        return {"success": bool(html), "html": html, "error": error or (None if html else "empty")}
    return fn


CLEAN_HTML = "<html>" + "x" * 600 + "</html>"          # 过长度门、无 bot 特征
BOT_HTML = "<html>Just a moment...</html>" + "y" * 600  # 够长但命中 Cloudflare 特征


# =========================================================================
# Quality gate（质量门三层判据）
# =========================================================================
def test_quality_gate_length():
    assert scrapers.quality_ok("x" * 499, "https://example.com") is False
    assert scrapers.quality_ok("x" * 500, "https://example.com") is True


def test_quality_gate_bot_markers():
    for marker in ("Just a moment", "Checking your browser", "Attention required"):
        assert scrapers.quality_ok(f"<html>{marker}</html>" + "z" * 600, "https://example.com") is False


def test_quality_gate_trending_structural_marker():
    # trending 页必须含 ≥5 个 Box-row article（与 radar.py 解析正则耦合）
    two_rows = "<html>" + '<article class="Box-row">' * 2 + "a" * 600 + "</html>"
    six_rows = "<html>" + '<article class="Box-row">' * 6 + "a" * 600 + "</html>"
    assert scrapers.quality_ok(two_rows, "https://github.com/trending?since=daily") is False
    assert scrapers.quality_ok(six_rows, "https://github.com/trending?since=daily") is True
    # 无结构标记的 URL 不做该判据
    assert scrapers.quality_ok(six_rows, "https://example.com") is True


def test_quality_gate_search_structural_marker():
    assert scrapers.quality_ok("<html>" + "data-view-component" * 2 + "a" * 600,
                               "https://github.com/search?q=x") is False
    assert scrapers.quality_ok("<html>" + "data-view-component" * 3 + "a" * 600,
                               "https://github.com/search?q=x") is True


# =========================================================================
# Tiered ladder（分级 fallback）
# =========================================================================
def test_tiered_first_quality_pass_wins():
    """httpx 拿到干净页面 → 直接返回，更重的引擎根本不动。"""
    calls = []
    def tracked(name, fn):
        def wrapped(url, timeout=90):
            calls.append(name)
            return fn(url, timeout)
        return wrapped

    with _mock_engines({
        "httpx": tracked("httpx", _fn(CLEAN_HTML)),
        "cloudscraper": tracked("cloudscraper", _fn(CLEAN_HTML)),
    }):
        html, engine = scrapers.fetch_html("https://example.com", strategy="tiered")
    assert engine == "httpx"
    assert html == CLEAN_HTML
    assert calls == ["httpx"], "tiered: 引擎过质量门后不得再跑更重的引擎"


def test_tiered_escalates_on_bot_check():
    """httpx 拿到 Cloudflare 中间页（够长但命中 bot 特征）→ 升级 cloudscraper。"""
    calls = []
    def tracked(name, fn):
        def wrapped(url, timeout=90):
            calls.append(name)
            return fn(url, timeout)
        return wrapped

    with _mock_engines({
        "httpx": tracked("httpx", _fn(BOT_HTML)),
        "cloudscraper": tracked("cloudscraper", _fn(CLEAN_HTML)),
    }):
        html, engine = scrapers.fetch_html("https://example.com", strategy="tiered")
    assert engine == "cloudscraper"
    assert calls == ["httpx", "cloudscraper"]


def test_tiered_escalates_on_missing_structural_marker():
    """trending 页 httpx 只拿到 2 个 Box-row（空壳页）→ 升级下一级拿到 6 个。"""
    shell = "<html>" + '<article class="Box-row">' * 2 + "a" * 600 + "</html>"
    full = "<html>" + '<article class="Box-row">' * 6 + "b" * 600 + "</html>"
    with _mock_engines({
        "httpx": _fn(shell),
        "cloudscraper": _fn(BOT_HTML),   # 又一个 bot 页 → 继续
        "playwright_stealth": _fn(full),
    }):
        html, engine = scrapers.fetch_html(
            "https://github.com/trending?since=daily", strategy="tiered"
        )
    assert engine == "playwright_stealth"
    assert '<article class="Box-row">' * 6 in html


def test_tiered_all_fail_returns_empty_none():
    """全部引擎失败/抛异常 → ("", "none")，无异常逃逸。"""
    with _mock_engines({
        "httpx": _fn(raises=True),
        "cloudscraper": _fn(""),
        "playwright_stealth": _fn(raises=True),
        "jina": _fn(""),
    }):
        assert scrapers.fetch_html("https://example.com", strategy="tiered") == ("", "none")


def test_tiered_best_effort_when_all_rejected():
    """全部过不了质量门但都有内容 → 回退返回最长的一个（调用方解析器兜底）。"""
    short_bot = "<html>Just a moment" + "a" * 500 + "</html>"
    long_bot = "<html>Just a moment" + "b" * 900 + "</html>"
    with _mock_engines({
        "httpx": _fn(short_bot),
        "cloudscraper": _fn(long_bot),
        "playwright_stealth": _fn(""),
        "jina": _fn(""),
    }):
        html, engine = scrapers.fetch_html("https://example.com", strategy="tiered")
    assert engine == "cloudscraper"
    assert len(html) == len(long_bot)


def test_tiered_exception_isolated():
    """某引擎抛异常 → 记录并跳过，不影响下一级。"""
    with _mock_engines({
        "httpx": _fn(raises=True),
        "cloudscraper": _fn(CLEAN_HTML),
    }):
        html, engine = scrapers.fetch_html("https://example.com", strategy="tiered")
    assert (html, engine) == (CLEAN_HTML, "cloudscraper")


def test_tiered_allowlist_blocks_disabled_engines():
    """firecrawl 模拟为可用且能拿到干净页面，但不在 config priority 白名单 → 永不运行。"""
    calls = []
    def fc(url, timeout=90):
        calls.append("firecrawl")
        return {"success": True, "html": CLEAN_HTML, "error": None}

    with _mock_engines({"httpx": _fn(CLEAN_HTML)}, extra_available=("firecrawl",)):
        # firecrawl available via extra mock, its scrape fn would win if it ran —
        # patch it in explicitly so we can observe calls
        with patch.dict("sys.modules", {
            "scrapers.firecrawl_scraper": MagicMock(is_available=lambda: True, scrape=fc)
        }):
            html, engine = scrapers.fetch_html("https://example.com", strategy="tiered")
    assert engine == "httpx"
    assert calls == [], "白名单外的引擎（不在 config priority）不得运行"


def test_serial_alias_skips_quality_gate():
    """strategy="serial"（= "first"）不做质量检查：短页面也算赢。"""
    with _mock_engines({
        "httpx": _fn("<html>short</html>"),
        "cloudscraper": _fn(CLEAN_HTML),
    }):
        html, engine = scrapers.fetch_html("https://example.com", strategy="serial")
    assert (html, engine) == ("<html>short</html>", "httpx")


# =========================================================================
# URL dispatcher
# =========================================================================
def test_select_engines_ladder_order():
    assert select_engines("https://github.com/trending") == [
        "httpx", "cloudscraper", "playwright_stealth", "jina"
    ]
    assert select_engines("https://huggingface.co/spaces/a/b") == ["httpx", "jina"]
    assert select_engines("https://example.com") == [
        "httpx", "cloudscraper", "playwright_stealth", "jina"
    ]


def test_quality_marker_lookup():
    assert quality_marker("https://github.com/trending?since=daily") == ('<article class="Box-row"', 5)
    assert quality_marker("https://github.com/search?q=x") == ("data-view-component", 3)
    assert quality_marker("https://example.com") is None


# =========================================================================
# Trending HTML parser tests (regression guard for regexes)
# =========================================================================
# ponytail: fixture matching the regexes in fetch_github_trending — regression guard
# for the parser itself (h2 href, lang itemprop, stars span, col-9 desc, stars today)
TRENDING_HTML = """
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/owner/ai-tool" data-view-component="true">ai-tool</a></h2>
  <p class="col-9 color-fg-muted my-1 pr-4"> An AI agent framework </p>
  <span itemprop="programmingLanguage">Python</span>
  <a class="Link--muted d-inline-block mr-3" href="/owner/ai-tool/stargazers">
    <svg .../> <span ...> 12,345 </span></a></span>
  <span class="d-inline-block float-sm-right"><svg .../> 234 stars today</span>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/other/llm-thing">llm-thing</a></h2>
  <p class="col-9 color-fg-muted my-1 pr-4"> LLM tool </p>
  <span itemprop="programmingLanguage">Rust</span>
  <span> 987 </span></a></span>
  <span> 12 stars today</span>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a data-hydro-click="x" href="https://github.com/abs/absolute-href">absolute-href</a></h2>
  <p class="col-9 color-fg-muted my-1 pr-4"> ABS-url variant GitHub serves some engines </p>
  <span itemprop="programmingLanguage">Go</span>
  <span> 555 </span></a></span>
  <span> 77 stars today</span>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/collections/some/list">not-a-repo</a></h2>
</article>
"""


def _fake_gh_repo(full_name):
    return {
        "name": full_name,
        "desc": f"desc of {full_name}",
        "url": f"https://github.com/{full_name}",
        "stars": 100,
        "forks": 1,
        "lang": "Python",
        "topics": ["llm"],
        "updated": "2026-08-20",
        "pushed": "2026-08-20",
        "score": 0,
    }


def test_fetch_github_trending_parses_scraper_html():
    """Scraper-tier HTML flows through the same parser: name/lang/stars/stars_today/desc
    extracted; non-repo paths (sponsors/) dropped; source=github_trending."""
    with (
        patch("scrapers.fetch_html", return_value=(TRENDING_HTML, "fixture")),
        patch("radar.gh_fetch_repo", side_effect=_fake_gh_repo),
    ):
        repos = radar.fetch_github_trending(since="daily", max_repos=30)
    names = [r["name"] for r in repos]
    assert names == ["owner/ai-tool", "other/llm-thing", "abs/absolute-href"]
    r0 = repos[0]
    assert r0["stars_today"] == 234
    assert r0["source"] == "github_trending"
    assert r0["stars"] == 100  # enriched from gh_fetch_repo, not the page's total
    assert r0["topics"] == ["llm"]


def test_fetch_github_trending_unparseable_falls_back():
    """Engine returns a bot-check page the regex can't parse → search-API proxy kicks in."""
    with (
        patch(
            "scrapers.fetch_html", return_value=("<html>sign in</html>", "httpx")
        ),
        patch(
            "radar.fetch_recent_active_repos",
            return_value=[{"name": "x/proxy", "stars": 1}],
        ) as fb,
    ):
        repos = radar.fetch_github_trending(since="daily", max_repos=30)
    assert repos == [{"name": "x/proxy", "stars": 1}]
    fb.assert_called_once()


def test_scraper_status_shape():
    st = scrapers.status()
    # status() 只覆盖 config.toml priority 白名单里的引擎（2026-09 起 4 个）
    assert set(st.keys()) == ACTIVE
    assert all(isinstance(v, bool) for v in st.values())


# =========================================================================
# Parallel-orchestration tests (strategy="parallel" — legacy/debug mode)
# =========================================================================
def _parallel_fake(
    *,
    httpx_html="",
    cs_html="",
    pw_html="",
    httpx_raise=False,
    cs_raise=False,
    pw_raise=False,
    pw_delay=0,
):
    """Build a 3-engine mock set. httpx/cloudscraper are sync (asyncio.to_thread in
    parallel mode); playwright_stealth has an async wrapper using asyncio.sleep (so the
    orchestrator can actually cancel it mid-flight via asyncio.wait).
    ponytail: pw_delay is the only knob that matters for parallel timeout tests — sync
    time.sleep inside an async fn would block the event loop and defeat cancellation."""

    def sync_fn(html, raises):
        def fn(url, timeout=90):
            if raises:
                raise RuntimeError(f"{html or 'engine'} boom")
            return {
                "success": bool(html),
                "html": html,
                "error": None if html else "empty",
            }

        return fn

    def async_fn(html, raises, delay):
        async def fn(url, timeout=90):
            if delay:
                await asyncio.sleep(delay)
            if raises:
                raise RuntimeError(f"{html or 'engine'} boom")
            return {
                "success": bool(html),
                "html": html,
                "error": None if html else "empty",
            }

        return fn

    mods = {
        "httpx_scraper": MagicMock(
            is_available=lambda: True, scrape=sync_fn(httpx_html, httpx_raise)
        ),
        "cloudscraper_scraper": MagicMock(
            is_available=lambda: True,
            scrape=sync_fn(cs_html, cs_raise),
            _async_scrape=async_fn(cs_html, cs_raise, 0),
        ),
        "playwright_stealth_scraper": MagicMock(
            is_available=lambda: True,
            scrape=sync_fn(pw_html, pw_raise),
            _async_scrape=async_fn(pw_html, pw_raise, pw_delay),
        ),
        # 其余 11 个引擎（含停用的 10 个 + jina）标记不可用，防止真实适配器混入
        "jina_scraper": MagicMock(is_available=lambda: False),
        **{
            f"{name}_scraper": MagicMock(is_available=lambda: False)
            for name in (
                "firecrawl", "crawl4ai", "playwright", "nodriver", "crawlee",
                "scrapy", "agent_reach", "trafilatura", "beautifulsoup", "drissionpage",
            )
        },
    }
    return patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in mods.items()})


def test_fetch_html_parallel_single_engine_wins():
    """Only one engine returns content; result uses that engine."""
    fake = _parallel_fake(httpx_html="<html>hx</html>", cs_html="", pw_html="")
    with fake:
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    assert html == "<html>hx</html>"
    assert engine == "httpx"


def test_fetch_html_parallel_all_fail_returns_empty_none():
    """Every engine raises; result is ("", "none"), no exception escapes."""
    fake = _parallel_fake(httpx_raise=True, cs_raise=True, pw_raise=True)
    with fake:
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    assert (html, engine) == ("", "none")


def test_fetch_html_parallel_longest_html_wins():
    """Multiple engines succeed → longest HTML wins; engine string lists every contributor."""
    fake = _parallel_fake(
        httpx_html="<html>short</html>",
        cs_html="<html>" + "x" * 5000 + "</html>",
        pw_html="<html>medium</html>",
    )
    with fake:
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    assert len(html) > 4000
    # Both httpx and cloudscraper succeeded (contributed html); engine field joins them
    parts = set(engine.split("+"))
    assert {"httpx", "cloudscraper"}.issubset(parts), f"missing contributors: {parts}"


def test_fetch_html_parallel_exception_isolated():
    """One engine raises; others still contribute; no crash."""
    fake = _parallel_fake(httpx_raise=True, cs_html="<html>cs-ok</html>", pw_html="")
    with fake:
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    assert html == "<html>cs-ok</html>"
    assert "cloudscraper" in engine


def test_fetch_html_parallel_respects_timeout():
    """A hanging engine is cancelled by the deadline; the other engines' results are kept."""
    fake = _parallel_fake(
        httpx_html="<html>on-time</html>",
        cs_html="",
        pw_html="<html>late</html>",
        pw_delay=5,
    )
    with fake:
        start = time.monotonic()
        html, engine = scrapers.fetch_html(
            "https://example.com", timeout=1, strategy="parallel"
        )
        elapsed = time.monotonic() - start
    assert html == "<html>on-time</html>"
    assert elapsed < 3, f"parallel mode blocked on slow engine ({elapsed:.1f}s)"


def test_fetch_html_parallel_priority_tiebreak():
    """When two engines return the SAME-length HTML, the higher-priority engine wins
    (httpx > cloudscraper) and is mentioned first in the engine string."""
    fake = _parallel_fake(
        httpx_html="<hx>" + "a" * 100 + "</hx>",
        cs_html="<cs>" + "b" * 100 + "</cs>",
        pw_html="",
    )
    with fake:
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    # httpx wins on tie → its HTML (containing the literal "<hx>" tag) is returned
    assert "<hx>" in html
    # engine string starts with the highest-priority contributor
    assert engine.split("+")[0] == "httpx"


if __name__ == "__main__":
    for name, fn in sorted(
        {
            k: v
            for k, v in list(globals().items())
            if k.startswith("test_") and callable(v)
        }.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
