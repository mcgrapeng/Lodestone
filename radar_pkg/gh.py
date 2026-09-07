# -*- coding: utf-8 -*-
"""radar_pkg.gh — GitHub 搜索(REST)/trending/单仓元数据。"""
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from radar_pkg import core

"""radar_pkg.gh — 由 radar.py 搬移(2026-09 架构拆分)。"""
def _search_pace():
    time.sleep(core._SEARCH_PACE["sleep"])

def gh_search(q, per_page=20):
    """Use gh CLI to search repos. Returns list of normalized repo dicts.
    ponytail: rate-limit recovery — sleep 60s + retry once on 403/secondary rate limit.
    Failures bump core.GH_SEARCH_STATS['failed'] so crawl() can report data quality."""
    cmd = [
        "gh",
        "api",
        "-X",
        "GET",
        "search/repositories",
        "-f",
        f"q={q}",
        "-f",
        "sort=stars",
        "-f",
        "order=desc",
        "-f",
        f"per_page={per_page}",
    ]
    for attempt in (1, 2):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                break
            stderr = r.stderr.strip()
            # ponytail: GitHub secondary rate limit → wait 60s, retry once, then pace slower
            if attempt == 1 and (
                "rate limit" in stderr.lower()
                or "403" in stderr
                or "secondary" in stderr.lower()
            ):
                print(
                    f"  ⏳ rate-limit hit on q={q[:60]!r}; sleeping 60s then retrying",
                    file=sys.stderr,
                )
                core._SEARCH_PACE["sleep"] = 6.0
                time.sleep(60)
                continue
            # ponytail: 2026-08 — on persistent gh api failure, fall back to scraping
            # the github.com search HTML page directly via the engine ladder
            # (httpx → cloudscraper → playwright_stealth → jina). Bypasses the
            # search-API secondary rate limit entirely.
            print(
                f"  ! gh api failed, falling back to HTML scrape: {stderr[:80]}",
                file=sys.stderr,
            )
            return _gh_search_html_fallback(q, per_page=per_page)
        except subprocess.TimeoutExpired:
            print(f"  ! gh api timeout (>60s) for q={q!r}; trying HTML", file=sys.stderr)
            return _gh_search_html_fallback(q, per_page=per_page)
        except Exception as e:
            print(f"  ! gh search error: {e}; trying HTML", file=sys.stderr)
            return _gh_search_html_fallback(q, per_page=per_page)
    else:
        # for/else runs only when the loop completes WITHOUT break — i.e. both
        # attempts failed without raising. Fall back to HTML scrape.
        return _gh_search_html_fallback(q, per_page=per_page)

    # ponytail: success path — gh api returned JSON; build the repo dict list
    # from `items`. Only reached when `break` exited the for-loop on attempt 1
    # or attempt 2 (after a 60s wait, gh api recovered).
    out = []
    for item in data.get("items", []):
        out.append(
            {
                "name": item["full_name"],
                "desc": (item.get("description") or "").strip(),
                "url": item["html_url"],
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
                "lang": item.get("language") or "—",
                "topics": item.get("topics", []) or [],
                "updated": item.get("updated_at", "")[:10],
                "pushed": item.get("pushed_at", "")[:10],
                "score": round(item.get("score", 0), 2),
            }
        )
    return out

def _parse_github_search_html(html: str) -> list:
    """Parse github.com/search HTML for repository cards.
    ponytail: GitHub's search HTML is JS-rendered for full data, but the SSR'd repo
    cards carry enough signals (name, description, language, stars, topics in
    data-ga-click attributes) for us to extract basic fields. We also pull
    stars from the <a href="/owner/repo/stargazers">123,456</a> pattern.
    """
    out: list[dict] = []
    # ponytail: extract owner/repo from <a class="Link" data-view-component href="/owner/repo">
    for m in re.finditer(
        r'<a[^>]+href="/([\w.-]+)/([\w.-]+)"[^>]*data-view-component[^>]*>([^<]+)</a>',
        html,
    ):
        owner, repo, name_text = m.group(1), m.group(2), m.group(3).strip()
        if not owner or not repo or owner in ("login", "logout", "settings", "notifications"):
            continue
        if repo in ("issues", "pulls", "actions", "projects", "wiki", "security"):
            continue
        # Approximate stars via aria-label or text near stargazers
        stars = 0
        # find next stargazers count in same article block
        block = html[m.start(): m.start() + 4000]
        s_m = re.search(
            r'href="/' + re.escape(owner) + r'/' + re.escape(repo)
            + r'/stargazers"[^>]*>.*?>([\d,\.]+)([kKmMbB]?)\s*</a>',
            block,
            re.DOTALL,
        )
        if s_m:
            num = s_m.group(1).replace(",", "")
            mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(
                s_m.group(2).lower(), 1
            )
            try:
                stars = int(float(num) * mult)
            except ValueError:
                pass
        # description
        d_m = re.search(
            r'<p class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL
        )
        desc = re.sub(r"<[^>]+>", "", d_m.group(1)).strip() if d_m else ""
        # language
        lang_m = re.search(
            r'itemprop="programmingLanguage">([^<]+)<', block
        )
        lang = lang_m.group(1).strip() if lang_m else "—"
        # topics: scrape from the badge list
        topics: list[str] = []
        for t_m in re.finditer(r'class="topic-tag[^"]*"[^>]*>([^<]+)<', block):
            topics.append(t_m.group(1).strip())
        out.append(
            {
                "name": f"{owner}/{repo}",
                "desc": desc[:300],
                "url": f"https://github.com/{owner}/{repo}",
                "stars": stars,
                "forks": 0,
                "lang": lang,
                "topics": topics,
                "updated": "",
                "pushed": "",
                "score": 0.0,
                "source": "github_search_html",
            }
        )
    # dedupe by name
    seen: set[str] = set()
    deduped: list[dict] = []
    for r in out:
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        deduped.append(r)
    return deduped

def _gh_search_html_fallback(q: str, per_page: int = 20) -> list:
    """Scrape github.com/search?q=<query>&type=repositories via the tiered engine ladder.
    Used when gh api search is rate-limited. Returns parsed repo dicts.
    ponytail: search HTML is JS-rendered; the SSR'd cards still carry name/desc/lang/stars
    which is enough for trending-style data. Stars are the only missing accurate field — we
    try to extract from the stargazers link pattern; if not found, leave as 0 (caller can
    enrich via gh_fetch_repo later).
    """
    url = (
        f"https://github.com/search?q={urllib.parse.quote(q)}"
        f"&type=repositories&s=stars&o=desc"
    )
    try:
        from scrapers import fetch_html

        html_text, engine = fetch_html(url, strategy="tiered", timeout=45)
    except Exception as e:
        print(f"  ! search-html fallback failed to even import scrapers: {e}", file=sys.stderr)
        core.GH_SEARCH_STATS["failed"] += 1
        return []
    if not html_text:
        print(f"  ! search-html fallback returned empty (engine={engine})", file=sys.stderr)
        core.GH_SEARCH_STATS["failed"] += 1
        return []
    parsed = _parse_github_search_html(html_text)
    if parsed:
        print(f"  · search-html via {engine}: {len(parsed)} repos (q={q[:60]!r})", file=sys.stderr)
        return parsed[:per_page]
    core.GH_SEARCH_STATS["failed"] += 1
    return []

def gh_fetch_repo(full_name):
    """Fetch a single repo's full metadata. Used for MANUAL_SEED_REPOS."""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return None
        item = json.loads(r.stdout)
    except Exception:
        return None
    return {
        "name": item["full_name"],
        "desc": (item.get("description") or "").strip(),
        "url": item["html_url"],
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "lang": item.get("language") or "—",
        "topics": item.get("topics", []) or [],
        "updated": item.get("updated_at", "")[:10],
        "pushed": item.get("pushed_at", "")[:10],
        "score": 0,
    }

def fetch_github_trending(since: str = "daily", max_repos: int = 30, language: str | None = None):
    """Scrape github.com/trending and enrich each entry with full data via gh_fetch_repo.

    Why: search-by-stars misses fresh AI tools that haven't crossed 5k yet but are trending today.
    HTML sources, in order (see scrapers/ — 4-engine tiered ladder, 2026-09):
      1. httpx → cloudscraper → playwright_stealth → jina (light→heavy→cloud,
         quality-gated: each tier must return a REAL trending page or we escalate)
      2. plain urllib (stdlib, original path)
      3. all failed → fetch_recent_active_repos (search-API proxy for trending)
    language: None = 全语言混合页;"python"/"typescript"/... = 语言子页(GitHub
    trending 无翻页,语言变体是唯一扩容手段 — 每页固定 25 条,max_repos>25 无效)。
    Returns normalized repo dicts (same shape as gh_search output) with extra 'source' marker.
    """
    lang_path = f"/{language}" if language else ""
    url = f"https://github.com/trending{lang_path}?since={since}"
    html_text, engine = "", "none"
    # tier 1: real scrapers — optional package; missing/broken → urllib still works.
    # ponytail: strategy="tiered" — engines escalate light→heavy; each result must
    # pass the quality gate (≥5 Box-row articles for trending) before it's accepted,
    # so a bot-check page from httpx escalates to cloudscraper instead of winning.
    try:
        from scrapers import fetch_html

        html_text, engine = fetch_html(url, strategy="tiered")
    except ImportError:
        pass
    # tier 2: stdlib urllib
    if not html_text:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            html_text = (
                urllib.request.urlopen(req, timeout=30)
                .read()
                .decode("utf-8", errors="replace")
            )
            engine = "urllib"
        except Exception as e:
            print(
                f"  ! github trending scrape failed ({e}); falling back to recent-active search",
                file=sys.stderr,
            )
            return fetch_recent_active_repos(max_repos=max_repos)
    else:
        print(f"  · trending html via {engine}")

    seeds = []
    seen = set()
    for art in re.findall(
        r'<article class="Box-row">(.+?)</article>', html_text, re.DOTALL
    ):
        # ponytail: href can be relative (/owner/repo) OR absolute (https://github.com/owner/repo)
        # depending on which GitHub variant the engine was served — accept both
        h2 = re.search(
            r'<h2[^>]*>\s*<a[^>]+href="(?:(?:https://github\.com)?/)?([^"]+)"', art
        )
        if not h2:
            continue
        name = h2.group(1).strip()
        # filter out sponsors/, apps/, and other non-repo paths
        parts = name.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            continue
        if name in seen:
            continue
        seen.add(name)
        lang_m = re.search(r'itemprop="programmingLanguage">([^<]+)<', art)
        lang = (lang_m.group(1).strip() if lang_m else None) or "—"
        stars_m = re.search(r"([\d,]+)\s*</span>\s*</a>\s*</span>", art)
        stars = int(stars_m.group(1).replace(",", "")) if stars_m else 0
        desc_m = re.search(r'<p class="col-9[^"]*"[^>]*>(.+?)</p>', art, re.DOTALL)
        desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
        # ponytail: github shows "X stars today" — that's the literal 24h delta we want for /api/gain
        today_m = re.search(r"([\d,]+)\s*stars\s*today", art)
        stars_today = int(today_m.group(1).replace(",", "")) if today_m else None
        seeds.append(
            {
                "name": name,
                "desc": desc,
                "stars": stars,
                "lang": lang,
                "stars_today": stars_today,
            }
        )
        if len(seeds) >= max_repos:
            break

    # ponytail: engine returned a page the regex can't parse (layout change / bot-check page
    # served raw) — search-API proxy beats an empty trending list
    if not seeds:
        print(
            f"  ! trending page parsed to 0 repos (engine={engine}); using recent-active search",
            file=sys.stderr,
        )
        return fetch_recent_active_repos(max_repos=max_repos)

    # Enrich each seed via gh_fetch_repo (core API, 5000/hr) — NOT gh_search, which would
    # burn 60 search-rate-limit slots (30/min) and trip secondary limits.
    out = []
    for s in seeds:
        r = gh_fetch_repo(s["name"])
        if r:
            r["source"] = "github_trending"
            # ponytail: carry over the "X stars today" parsed from the trending HTML so
            # upsert_repos can persist the 24h delta.
            r["stars_today"] = s.get("stars_today")
            out.append(r)
        else:
            # fallback: synthesize minimal dict (no topics → will fail is_ai_relevant, dropped)
            out.append(
                {
                    "name": s["name"],
                    "url": f"https://github.com/{s['name']}",
                    "desc": s["desc"],
                    "stars": s["stars"],
                    "forks": 0,
                    "lang": s["lang"],
                    "topics": [],
                    "source": "github_trending",
                    "stars_today": s.get("stars_today"),
                    "updated": "",
                    "pushed": "",
                    "score": 0,
                }
            )
    return out

def fetch_recent_active_repos(max_repos: int = 30, days_back: int = 7) -> list:
    """Fallback for github.com/trending scrape — use gh search API by recent push + AI topics.
    ponytail: github.com/trending HTML is JS-rendered, urllib can't see the repo list. Use the
    search API instead: pushed:>N days ago + AI topic + stars sort. This gives us "recently
    active high-star AI repos", which is the closest proxy for trending.
    """
    # compute cutoff date
    import datetime as _dt

    cutoff = (_dt.date.today() - _dt.timedelta(days=days_back)).isoformat()
    # 2026-09 P3: topic:ai → 硬 topic 组。裸 'ai' 是宽 topic(is_ai_relevant 也不认),
    # 捞回来的多是非 AI 项目又被过滤掉,兜底几乎白跑。
    queries = [
        f"stars:>300 pushed:>{cutoff} topic:llm",
        f"stars:>300 pushed:>{cutoff} topic:ai-agent",
        f"stars:>300 pushed:>{cutoff} topic:claude-code",
        f"stars:>300 pushed:>{cutoff} topic:mcp-server",
    ]
    seen = set()
    out = []
    for q in queries:
        try:
            hits = gh_search(q, per_page=20)
        except Exception as e:
            print(f"  ! recent-active query failed: {q}: {e}", file=sys.stderr)
            continue
        for r in hits:
            n = r.get("name")
            if not n or n in seen:
                continue
            seen.add(n)
            r["source"] = "recent_active"
            r["stars_today"] = None  # we don't have a true daily delta
            out.append(r)
            if len(out) >= max_repos:
                break
        if len(out) >= max_repos:
            break
    return out

def _gh_repo_meta(full_name: str) -> dict | None:
    """Query GitHub via `gh` for {stars, topics, pushed_at, description}. Caches per process.
    Returns None if `gh` unavailable or repo private/missing."""
    if not full_name or "/" not in full_name:
        return None
    # ponytail: per-function cache via monkey-patch attribute. Avoids module-level
    # mutable state and survives reloads. Pyright doesn't know about the runtime
    # attribute set on FunctionType, so silence the false positive here.
    if not hasattr(_gh_repo_meta, "_cache"):
        _gh_repo_meta._cache = {}  # type: ignore[attr-defined]
    cache: dict = _gh_repo_meta._cache  # type: ignore[attr-defined]
    if full_name in cache:
        return cache[full_name]
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            cache[full_name] = None
            return None
        data = json.loads(r.stdout)
        out = {
            "name": data.get("full_name"),
            "url": data.get("html_url"),
            "stars": data.get("stargazers_count") or 0,
            "topics": data.get("topics") or [],
            "pushed_at": data.get("pushed_at"),
            "description": data.get("description"),
        }
        cache[full_name] = out
        return out
    except Exception:
        cache[full_name] = None
        return None
