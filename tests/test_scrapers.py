"""Tests for scrapers/ chain + trending HTML parse. Run: python3 -m tests.test_scrapers"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
import radar
import scrapers


# =========================================================================
# Serial-fallback tests (strategy="serial") — document the strict contract
# =========================================================================
def test_fetch_html_first_success_wins():
    """Serial chain: firecrawl → crawl4ai → playwright; first non-empty html wins."""
    calls = []

    def fc(url, timeout=90):
        calls.append("firecrawl")
        return {"success": True, "html": "<html>fc</html>", "error": None}

    def c4(url, timeout=90):
        calls.append("crawl4ai")
        return {"success": True, "html": "<html>c4</html>", "error": None}

    fake = {
        "firecrawl_scraper": MagicMock(is_available=lambda: True, scrape=fc),
        "crawl4ai_scraper": MagicMock(is_available=lambda: True, scrape=c4),
        "playwright_scraper": MagicMock(is_available=lambda: False),
    }
    with patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in fake.items()}):
        html, engine = scrapers.fetch_html("https://example.com", strategy="serial")
    assert (html, engine) == ("<html>fc</html>", "firecrawl")
    assert calls == ["firecrawl"], (
        "serial mode: engines after first success must not run"
    )


def test_fetch_html_falls_through_failures():
    """Serial mode: a failing engine is logged + skipped; next engine is tried;
    all-fail → ("", "none")."""

    def bad(url, timeout=90):
        return {"success": False, "html": "", "error": "boom"}

    def raise_(url, timeout=90):
        raise RuntimeError("crash")

    def good(url, timeout=90):
        return {"success": True, "html": "<html>pw</html>", "error": None}

    fake = {
        "firecrawl_scraper": MagicMock(is_available=lambda: True, scrape=bad),
        "crawl4ai_scraper": MagicMock(is_available=lambda: True, scrape=raise_),
        "playwright_scraper": MagicMock(is_available=lambda: True, scrape=good),
    }
    with patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in fake.items()}):
        html, engine = scrapers.fetch_html("https://example.com", strategy="serial")
    assert (html, engine) == ("<html>pw</html>", "playwright")

    fake_all_bad = {
        "firecrawl_scraper": MagicMock(is_available=lambda: True, scrape=bad),
        "crawl4ai_scraper": MagicMock(is_available=lambda: True, scrape=bad),
        "playwright_scraper": MagicMock(is_available=lambda: True, scrape=bad),
    }
    with patch.dict(
        "sys.modules", {f"scrapers.{k}": v for k, v in fake_all_bad.items()}
    ):
        assert scrapers.fetch_html("https://example.com", strategy="serial") == (
            "",
            "none",
        )


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
            "scrapers.fetch_html", return_value=("<html>sign in</html>", "firecrawl")
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
    assert set(st.keys()) == {"firecrawl", "crawl4ai", "playwright"}
    assert all(isinstance(v, bool) for v in st.values())


# =========================================================================
# Parallel-orchestration tests (strategy="parallel")
# =========================================================================
def _parallel_fake(
    *,
    fc_html="",
    c4_html="",
    pw_html="",
    fc_raise=False,
    c4_raise=False,
    pw_raise=False,
    c4_delay=0,
):
    """Build a 3-engine mock set. firecrawl is sync (uses asyncio.to_thread in parallel mode);
    crawl4ai/playwright have an async wrapper that uses asyncio.sleep (so the orchestrator
    can actually cancel them mid-flight via asyncio.wait).
    ponytail: c4_delay is the only knob that matters for parallel timeout tests — sync
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

    return {
        "firecrawl_scraper": MagicMock(
            is_available=lambda: True, scrape=sync_fn(fc_html, fc_raise)
        ),
        "crawl4ai_scraper": MagicMock(
            is_available=lambda: True,
            scrape=sync_fn(c4_html, c4_raise),
            _async_scrape=async_fn(c4_html, c4_raise, c4_delay),
        ),
        "playwright_scraper": MagicMock(
            is_available=lambda: True,
            scrape=sync_fn(pw_html, pw_raise),
            _async_scrape=async_fn(pw_html, pw_raise, 0),
        ),
    }


def test_fetch_html_parallel_single_engine_wins():
    """Only one engine returns content; result uses that engine."""
    fake = _parallel_fake(fc_html="<html>fc</html>", c4_html="", pw_html="")
    with patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in fake.items()}):
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    assert html == "<html>fc</html>"
    assert engine == "firecrawl"


def test_fetch_html_parallel_all_fail_returns_empty_none():
    """Every engine raises; result is ("", "none"), no exception escapes."""
    fake = _parallel_fake(fc_raise=True, c4_raise=True, pw_raise=True)
    with patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in fake.items()}):
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    assert (html, engine) == ("", "none")


def test_fetch_html_parallel_longest_html_wins():
    """Multiple engines succeed → longest HTML wins; engine string lists every contributor."""
    fake = _parallel_fake(
        fc_html="<html>short</html>",
        c4_html="<html>" + "x" * 5000 + "</html>",
        pw_html="<html>medium</html>",
    )
    with patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in fake.items()}):
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    assert len(html) > 4000
    # Both firecrawl and crawl4ai succeeded (contributed html); engine field joins them
    parts = set(engine.split("+"))
    assert {"firecrawl", "crawl4ai"}.issubset(parts), f"missing contributors: {parts}"


def test_fetch_html_parallel_exception_isolated():
    """One engine raises; others still contribute; no crash."""
    fake = _parallel_fake(fc_raise=True, c4_html="<html>c4-ok</html>", pw_html="")
    with patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in fake.items()}):
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    assert html == "<html>c4-ok</html>"
    assert "crawl4ai" in engine


def test_fetch_html_parallel_respects_timeout():
    """A hanging engine is cancelled by the deadline; the other engines' results are kept."""
    fake = _parallel_fake(
        fc_html="<html>on-time</html>",
        c4_html="<html>late</html>",
        c4_delay=5,
        pw_html="",
    )
    with patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in fake.items()}):
        start = time.monotonic()
        html, engine = scrapers.fetch_html(
            "https://example.com", timeout=1, strategy="parallel"
        )
        elapsed = time.monotonic() - start
    assert html == "<html>on-time</html>"
    assert elapsed < 3, f"parallel mode blocked on slow engine ({elapsed:.1f}s)"


def test_fetch_html_parallel_priority_tiebreak():
    """When two engines return the SAME-length HTML, the higher-priority engine wins
    (firecrawl > crawl4ai > playwright) and is mentioned first in the engine string."""
    fake = _parallel_fake(
        fc_html="<fc>" + "a" * 100 + "</fc>",
        c4_html="<c4>" + "b" * 100 + "</c4>",
        pw_html="",
    )
    with patch.dict("sys.modules", {f"scrapers.{k}": v for k, v in fake.items()}):
        html, engine = scrapers.fetch_html("https://example.com", strategy="parallel")
    # firecrawl wins on tie → its HTML (containing the literal "<fc>" tag) is returned
    assert "<fc>" in html
    # engine string starts with the highest-priority contributor
    assert engine.split("+")[0] == "firecrawl"


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
