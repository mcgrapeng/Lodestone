# -*- coding: utf-8 -*-
"""radar_pkg.crawl — 爬取编排(分类/5k/新星/trending → 过滤 → 翻译 → 入库)。"""

import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from radar_pkg import core
import db
from radar_pkg.core import (
    AI_TOPIC_BLOCKLIST,
    CATEGORIES,
    CRAWL_LOCK,
    CRAWL_LOCK_STALE_S,
    CURATED_ALLOWLIST,
    DATA,
    MANUAL_SEED_REPOS,
    TOP_5K_LIMIT,
    TOP_5K_QUERIES,
    facts_for_repo,
    is_ai_relevant,
    is_finance_blocked,
    normalize_git_url,
)
from radar_pkg.detect import detect_local_skills
from radar_pkg.gh import fetch_github_trending, gh_fetch_repo, gh_search, _search_pace
from radar_pkg.match import (
    _annotate_local_installed,
    _build_plugin_segs,
    _installed_segments,
)
from radar_pkg.translate import enrich_summaries, translate_batch


def acquire_crawl_lock() -> bool:
    """True = acquired (caller must release); False = another crawl is running."""
    try:
        fd = os.open(CRAWL_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            if time.time() - CRAWL_LOCK.stat().st_mtime > CRAWL_LOCK_STALE_S:
                CRAWL_LOCK.unlink(missing_ok=True)
                return acquire_crawl_lock()
        except OSError:
            pass
        return False


def release_crawl_lock():
    CRAWL_LOCK.unlink(missing_ok=True)


def crawl_lock_held() -> bool:
    """Non-acquiring check for the API layer (returns 409 instead of spawning)."""
    if not CRAWL_LOCK.exists():
        return False
    try:
        if time.time() - CRAWL_LOCK.stat().st_mtime > CRAWL_LOCK_STALE_S:
            return False
    except OSError:
        return False
    return True


def crawl():
    """Fetch all categories, dedupe, save. File-locked — one crawl at a time."""
    if not acquire_crawl_lock():
        print("[crawl] another crawl is already running — aborting", file=sys.stderr)
        return {"ok": False, "error": "crawl already running"}
    try:
        return _crawl_inner()
    finally:
        release_crawl_lock()


def _crawl_inner():
    """Fetch all categories, dedupe, save."""
    today = datetime.date.today().isoformat()
    core.GH_SEARCH_STATS["failed"] = 0
    print(f"[crawl] {today} — {len(CATEGORIES)} categories")
    try:
        from scrapers import status as scraper_status

        avail = [k for k, v in scraper_status().items() if v]
        print(
            f"[crawl] scrapers: {', '.join(avail) if avail else 'none (urllib only)'}"
        )
    except ImportError:
        print("[crawl] scrapers: none (scrapers/ package missing; urllib only)")
    cat_results = []

    # ponytail: 2026-09 — GraphQL 批量搜索。全部 GitHub query（20 分类 ~119 条 +
    # 5k+ pass 85 条）先收集、去重、分批并行执行（分类批 6×first:30，5k 批
    # 8×first:50；失败批对半拆分重试）。实测搜索阶段 ~12 分钟（串行 REST）→
    # ~3 分钟（2026-09 全量验证：204 query 中 189 个走 GraphQL，15 个 REST 兜底）。
    # GraphQL 彻底失败的 query 回退 REST gh_search（自适应 pace + HTML 兜底）。
    _search_t0 = time.monotonic()
    _all_gh_queries = [q for cat in CATEGORIES for q in cat.get("queries", [])]
    _batch: dict[str, list] = {}
    _new_star_queries: list[str] = []  # GraphQL 不可用时保持空(新星通道仅依赖 GraphQL)
    _new_star_cutoff = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    try:
        from sources.github_graphql import gh_search_batch

        print(
            f"[crawl] GraphQL batch search: {len(_all_gh_queries)} category queries "
            f"+ {len(TOP_5K_QUERIES)} 5k+ queries…"
        )
        _batch.update(gh_search_batch(_all_gh_queries, per_page=30, batch_size=6))
        _batch.update(
            gh_search_batch(
                TOP_5K_QUERIES, per_page=50, batch_size=8, follow_page2=True
            )
        )
        # ponytail: 2026-09 P1 修复 — 低星新星通道。全部 5k 池查询 stars:>500、
        # 分类查询大多 stars:>100+，"刚开源、<500 星、没上 trending"的项目有
        # 真空期（实测 PG 中 stars<500 且无分类的行 = 0）。近 14 天 created +
        # 硬 topic + stars:>50 专门捞这批；走独立通道并入（不参与星标截断）。
        _new_star_queries = [
            f"stars:>50 created:>{_new_star_cutoff} topic:{t}"
            for t in ("llm", "ai-agent", "mcp-server", "claude-code", "ai-coding")
        ]
        _batch.update(gh_search_batch(_new_star_queries, per_page=30, batch_size=6))
    except Exception as e:
        print(
            f"  [warn] GraphQL batch unavailable ({e}); REST serial fallback "
            f"({len(_all_gh_queries) + len(TOP_5K_QUERIES)} queries, slow)",
            file=sys.stderr,
        )

    def _query_repos(q: str, per_page: int = 20) -> list:
        """批量结果优先；GraphQL 没覆盖到的 query 回退 REST gh_search。"""
        if q in _batch:
            return _batch[q]
        _search_pace()  # rate limit: 30 search req/min — adaptive sleep between ALL search calls
        try:
            repos = gh_search(q, per_page=per_page)
        except Exception as e:
            print(f"  [warn] query '{q}' failed: {e}", file=sys.stderr)
            repos = []
        _batch[q] = repos
        return repos

    for cat in CATEGORIES:
        seen = set()
        repos = []
        # ponytail: empty `queries` = non-GitHub source category. Dispatch by the
        # `source` field so adding new sources (HF Spaces, HF Models, MCP Registry,
        # ...) is a single line. Keeps the rest of the pipeline (translation,
        # hot_now, upsert, JSON snapshot) working uniformly.
        if not cat["queries"]:
            src = cat.get("source")
            if src == "hf_spaces":
                repos = fetch_huggingface_trending(max_items=30)
            elif src == "hf_models":
                try:
                    from sources.huggingface_models import (
                        fetch_huggingface_models_trending,
                    )

                    repos = fetch_huggingface_models_trending(max_items=30)
                except Exception as e:
                    print(f"  [warn] HF models fetcher failed: {e}", file=sys.stderr)
                    repos = []
            elif src == "mcp_registry":
                try:
                    from sources.mcp_registry import fetch_mcp_registry

                    repos = fetch_mcp_registry(max_items=30)
                except Exception as e:
                    print(f"  [warn] MCP registry fetcher failed: {e}", file=sys.stderr)
                    repos = []
            elif src == "arxiv":
                try:
                    from sources.arxiv_papers import fetch_arxiv_recent

                    repos = fetch_arxiv_recent(max_items=30)
                except Exception as e:
                    print(f"  [warn] arXiv fetcher failed: {e}", file=sys.stderr)
                    repos = []
            # else: an unknown source type — drop with warning so silent data loss is loud
            if not repos and src:
                print(
                    f"  [warn] category {cat['id']!r}: source {src!r} returned 0 items",
                    file=sys.stderr,
                )
        else:
            for q in cat["queries"]:
                for r in _query_repos(q, per_page=30):
                    # ponytail: 2026-09 — 分类结果过完整 AI 过滤。宽 query
                    # （topic:workflow-orchestration 等）会带进 airflow/nvm 这类
                    # 非 AI 项目；AI_TOPIC_HARD 已补齐变体（vision-language-model/
                    # mcp/...）避免误伤 Qwen-VL/playwright-mcp。
                    if not is_ai_relevant(r):
                        continue
                    ukey = normalize_git_url(r.get("url")) or r["name"]
                    if ukey in seen:
                        continue
                    seen.add(ukey)
                    repos.append(r)
        # sort by stars desc
        repos.sort(key=lambda x: x["stars"], reverse=True)
        repos = repos[:30]
        cat_results.append(
            {
                "id": cat["id"],
                "name": cat["name"],
                "desc": cat["desc"],
                "count": len(repos),
                "repos": repos,
            }
        )
        print(f"  ✓ {cat['name']}: {len(repos)} repos")

    # ponytail: 5k+ pass — catch mainstream AI tools not matched by category queries
    print(f"[crawl] 5k+ pass ({len(TOP_5K_QUERIES)} queries)…")
    # ponytail: 2026-09 P2 — 池内合并键统一小写:GitHub full_name 大小写随改名
    # 变化,精确比较会产生大小写变体漏合并(单次 crawl 内 normalize_git_url 已
    # 小写,这里对齐同一语义;repo["name"] 原样保留供显示)。
    top_5k_repos = {}
    for q in TOP_5K_QUERIES:
        try:
            for r in _query_repos(q, per_page=100):
                if not is_ai_relevant(r):
                    continue
                top_5k_repos.setdefault(r["name"].lower(), r)
        except Exception as e:
            print(f"  [warn] 5k+ query '{q}' failed: {e}")

    print(
        f"  ✓ 5k+ pass: {len(top_5k_repos)} repos after AI filter "
        f"(search phase {time.monotonic() - _search_t0:.0f}s)"
    )

    # ponytail: manual seed — guaranteed inclusion of well-known AI tools that escape topic search
    for full_name in MANUAL_SEED_REPOS:
        if full_name.lower() in top_5k_repos:
            continue
        r = gh_fetch_repo(full_name)
        if not r or not is_ai_relevant(r):
            continue
        top_5k_repos[full_name.lower()] = r
        print(f"  ✓ manual seed: {full_name} ({r['stars']} ⭐)")

    # ponytail: GitHub trending — catches fresh AI tools with <5k stars that are hot today.
    # Pull BOTH daily and weekly — daily = today's buzz, weekly = rising stars the daily
    # doesn't yet show. Dedupe on name so a repo on both lists is counted once.
    # 2026-09 P2 — daily 加语言子页(python/typescript/rust/go,各 25 条):GitHub
    # trending 无翻页、全语言混合页每天只捞出 ~22 个 AI 项目,语言变体是唯一
    # 扩容手段。6 路并发(各走分级引擎阶梯),失败一路不拖累其余。
    _trend_routes = [
        ("daily", None),
        ("weekly", None),
        ("daily", "python"),
        ("daily", "typescript"),
        ("daily", "rust"),
        ("daily", "go"),
    ]
    print(
        f"[crawl] GitHub trending ({len(_trend_routes)} routes: daily/weekly × all-lang + python/ts/rust/go)…"
    )
    trending_daily, trending_weekly, _trend_lang = [], [], []
    with ThreadPoolExecutor(max_workers=len(_trend_routes)) as _tex:
        _futs = {
            _tex.submit(fetch_github_trending, since, 30, lang): (since, lang)
            for since, lang in _trend_routes
        }
        for _fut, (_since, _lang) in _futs.items():
            try:
                _res = _fut.result()
            except Exception as e:
                print(
                    f"  [warn] trending {_since}/{_lang or 'all'} failed: {e}",
                    file=sys.stderr,
                )
                continue
            if _lang is None:
                if _since == "daily":
                    trending_daily = _res
                else:
                    trending_weekly = _res
            else:
                _trend_lang.extend(_res)
    trending_seen, trending = set(), []
    for r in trending_daily + trending_weekly + _trend_lang:
        if r["name"].lower() in trending_seen:
            continue
        trending_seen.add(r["name"].lower())
        trending.append(r)
    # ponytail: 2026-09 P3 — 不在 trending 路径上跑 is_ai_relevant 拒数据.
    # github.com/trending 是 GitHub 的人工策展榜,本身就是 AI 相关性信号.
    # 此前 is_ai_relevant 三道闸门会因 microsoft-office/docx 等 topic 把
    # microsoft/markitdown 这类"借 langchain/openai 集成"的项目挡掉,导致
    # /api/gain 24h 星增 Top 卡片无 desc_zh/summary_zh. 现在只在合入 5k 池
    # 时跑 AI 过滤,trending 原样进入 stars_today + trending[] 列表,
    # /api/gain 卡片能拿到完整字段.
    for r in trending:
        if r["name"].lower() not in top_5k_repos:
            # 合入 5k 池前仍过 AI 过滤 — 防 nvm 这类非 AI 热门项目污染 hot_now
            if is_ai_relevant(r):
                top_5k_repos[r["name"].lower()] = r
    trending_ai = list(trending)  # 全部 trending 都算 AI-related(github 策展保证)
    print(
        f"  ✓ trending: {len(trending_daily)} daily + {len(trending_weekly)} weekly + "
        f"{len(_trend_lang)} lang-variant → {len(trending)} unique → {len(trending_ai)} AI-relevant → merged into 5k+ pool"
    )
    # ponytail: keep trending SEPARATELY so the 300-row TOP_5K_LIMIT truncation below can't
    # drop their stars_today. Trending repos are low-star by definition (the whole point is
    # "new today" / "rising this week") — they'd otherwise be at the bottom of the 300-row slice.
    top_5k_sorted = sorted(
        top_5k_repos.values(), key=lambda x: x.get("stars", 0), reverse=True
    )[:TOP_5K_LIMIT]

    # Detect local skills — cached 60s; crawl marks which repos are already installed
    # 2026-09: 与 serve/refresh 路径对齐 — 复用 _installed_segments(skills origin +
    # marketplace + 插件 origin)并小写化,而非裸技能目录名大小写敏感匹配
    local = detect_local_skills()
    installed_full = {s.lower() for s in _installed_segments(local)}
    installed_segs = {
        *installed_full,
        *(s.split("/")[-1] for s in installed_full),
        *(
            p["name"].split("@")[0].lower()
            for p in (local.get("plugins") or [])
            if p.get("name")
        ),
    }
    print(f"[crawl] local installed (full/seg): {len(installed_segs)}")

    # ponytail: build flat deduped list of (cats ∪ 5k+); assign best_category; is_ai_relevant
    to_persist = []
    cat_pairs = []  # (repo_name, category_id) for repo_categories
    for cat in cat_results:
        for r in cat["repos"]:
            r["best_category"] = cat["id"]
            to_persist.append(r)
            cat_pairs.append((r["name"], cat["id"]))
    for r in top_5k_sorted:
        r["best_category"] = None  # 5k+ doesn't belong to a single category
        to_persist.append(r)
    # ponytail: trending repos get stars_today which is the entire signal for /api/gain.
    # The TOP_5K_LIMIT truncation above drops low-star trending repos — re-add them
    # so the stars_today field always reaches the DB / JSON snapshot.
    for r in trending_ai:
        if r["name"].lower() not in {p["name"].lower() for p in to_persist}:
            r["best_category"] = None
            to_persist.append(r)

    # ponytail: 2026-09 P1 — 新星通道并入(同 trending 补回逻辑:不参与星标截断;
    # 已在分类/5k/trending 里的不会重复并入;键统一小写防大小写变体漏判)。
    new_stars: dict[str, dict] = {}
    for q in _new_star_queries:
        for r in _batch.get(q) or []:
            if not is_ai_relevant(r):
                continue
            new_stars.setdefault(r["name"].lower(), r)
    _ns_existing = {p["name"].lower() for p in to_persist}
    for r in new_stars.values():
        if r["name"].lower() not in _ns_existing:
            r["best_category"] = None
            to_persist.append(r)
    print(
        f"  ✓ new-star pass: {len(new_stars)} low-star repos (created>{_new_star_cutoff if _new_star_queries else '—'})"
    )
    # ponytail: 去重规则 = git 完整仓库地址（normalize_git_url 归一化：小写/
    # 去 .git/去尾斜杠/gh:// 前缀）。同一仓库从 GitHub 搜索、trending、MCP
    # registry 多路进来只会留一份（分类归属仍是多对多）。
    # 2026-09：trending 标记在去重时打上 — JSON 快照此前 0 标记，前端「趋势」
    # tab 一直在显示按星标排序的兜底数据，与 github.com/trending 对不上。
    _trending_names = {r["name"].lower() for r in trending_ai}
    seen = set()
    deduped = []
    for r in to_persist:
        ukey = normalize_git_url(r.get("url")) or r["name"]
        if ukey in seen:
            continue
        seen.add(ukey)
        r["is_ai_relevant"] = is_ai_relevant(r)
        if r["name"].lower() in _trending_names:
            r["trending"] = True
        deduped.append(r)

    # ponytail: 2026-09 — SKILL.md 探测。不是所有 GitHub 项目都支持安装为 skill
    # （只有含 SKILL.md / skill.md / SKILL.yaml 的才是）。在翻译前探测，结果写
    # 入每个 repo 的 is_skill 字段，前端据此门控「安装为 Skill」按钮。
    try:
        from radar_pkg.skill_probe import annotate_repos

        annotate_repos(deduped, max_workers=8)
    except Exception as e:
        print(f"  [warn] skill probe failed: {e}", file=sys.stderr)

    # ponytail: translate once, cache forever — descriptions don't change day-to-day
    print("[crawl] translating to Chinese…")
    pairs = [(f"{r['name']}::desc", r.get("desc", "")) for r in deduped]
    zh = translate_batch(pairs)
    for r in deduped:
        r["desc_zh"] = zh.get(f"{r['name']}::desc", "") or r.get("desc_zh", "")
        r["facts"] = facts_for_repo(r)
        r["local_installed"] = (
            r["name"].lower() in installed_segs
            or r["name"].split("/")[-1].lower() in installed_segs
        )
        # 精选赛道标记 — hot_now 保底浮出用（CURATED_ALLOWLIST + 手工种子）
        r["curated"] = (r["name"].lower() in CURATED_ALLOWLIST) or (
            r["name"] in MANUAL_SEED_REPOS
        )

    # ponytail: 2026-09 — 详细中文描述（README 首段翻译，缓存复用）。
    # 取代抽屉里的按需「中文详介」— 数据随快照就绪，前端零等待。
    try:
        n_sum = enrich_summaries(deduped)
        print(f"  ✓ summaries: {n_sum}/{len(deduped)} repos with zh summary")
    except Exception as e:
        print(f"  [warn] summary enrichment failed: {e}", file=sys.stderr)
        for r in deduped:
            r.setdefault("summary_zh", r.get("desc_zh") or "")

    # ponytail: 2026-09 — LLM 5 维度决策分析（什么 / 痛点 / 竞品 / 优缺 / 何时选）。
    # 仅在配置 ANTHROPIC_API_KEY / OPENAI_API_KEY / OLLAMA_HOST 时启用；否则降级
    # 到 summary_sections 三桶 README 摘要。增量分析 — cache 命中跳过。
    try:
        from radar_pkg.llm_analyze import analyze_many

        # ponytail: 把已缓存的 raw README 喂给 LLM 模块 — 避免再走 GitHub
        import json as _json

        readme_cache: dict = {}
        if core.README_ZH_CACHE.exists():
            try:
                readme_cache = _json.loads(core.README_ZH_CACHE.read_text())
            except Exception:
                readme_cache = {}
        llm_inputs = []
        for r in deduped:
            entry = readme_cache.get((r.get("name") or "").lower()) or {}
            r["analysis_5d"] = entry.get("analysis_5d") or readme_cache.get(
                (r.get("name") or "").lower(), {}
            ).get("analysis_5d")
            if entry.get("raw_md"):
                llm_inputs.append(
                    {
                        "name": r["name"],
                        "readme": entry["raw_md"],
                        "topics": r.get("topics") or [],
                        "lang": r.get("lang"),
                        "stars": r.get("stars") or 0,
                    }
                )
        if llm_inputs:
            n = analyze_many(llm_inputs, max_workers=4)
            print(f"  ✓ llm analysis: {n} repos got 5d analysis")
            # ponytail: 把分析结果回写到 readme_zh_cache（共享缓存文件，避免再开一个）
            for inp in llm_inputs:
                key = inp["name"].lower()
                if key in readme_cache:
                    # 重新加载刚写入的 llm cache，取最新
                    try:
                        from radar_pkg.llm_analyze import _load_cache as _load_llm_cache

                        llm_cache = _load_llm_cache()
                        if key in llm_cache:
                            readme_cache[key]["analysis_5d"] = llm_cache[key]
                            for r in deduped:
                                if (r.get("name") or "").lower() == key:
                                    r["analysis_5d"] = llm_cache[key]
                                    break
                    except Exception:
                        pass
            # 把 analysis_5d 落回 readme_zh_cache.json
            try:
                core.README_ZH_CACHE.write_text(
                    _json.dumps(readme_cache, ensure_ascii=False, indent=1)
                )
            except Exception as e:
                print(f"  [warn] write analysis_5d back to cache: {e}", file=sys.stderr)
    except Exception as e:
        print(f"  [warn] llm analysis failed: {e}", file=sys.stderr)

    failed = core.GH_SEARCH_STATS["failed"]
    if failed:
        print(
            f"  [warn] {failed} GitHub queries failed this run — data may be incomplete",
            file=sys.stderr,
        )

    # ponytail: write everything to Postgres in one transaction; ANY PG failure (pg8000
    # missing, PG down) falls back to JSON so /api/data + today() still work.
    import db

    if db._DB_OK:
        conn = None
        try:
            db.ensure_database()
            db.ensure_schema()
            conn = db.connect()
            cur = conn.cursor()
            cur.execute("INSERT INTO crawl_log DEFAULT VALUES RETURNING id")
            crawl_id = cur.fetchone()[0]
            n_inserted, n_updated = db.upsert_repos(conn, deduped)
            # ponytail: 2026-09 — cat_pairs 必须按 deduped 过滤。分类循环收集的
            # 关联在全局去重后可能指向被丢弃的条目(实测 MCP registry 项的
            # websiteUrl 归一化后与别的条目撞键被 dedup 丢弃),外键约束会让
            # 整个入库事务回滚 → JSON fallback,PG 数据停在旧 crawl。
            _persisted_names = {r["name"] for r in deduped}
            db.replace_categories(
                conn,
                [(n, c) for n, c in cat_pairs if n in _persisted_names],
            )
            db.snapshot_stars(conn, [r["name"] for r in deduped])
            # ponytail: trending flag is recomputed each crawl — clear stale, then set today's trending repos
            db.set_trending(conn, [r["name"] for r in trending_ai])
            cur.execute(
                "UPDATE crawl_log SET finished_at = NOW(), repos_seen = %s, repos_added = %s,"
                " repos_updated = %s, queries_failed = %s WHERE id = %s",
                (len(deduped), n_inserted, n_updated, failed, crawl_id),
            )
            conn.commit()
            print(
                f"[crawl] saved → postgres ai_radar ({n_inserted} added, {n_updated} updated, {len(deduped)} unique this run)"
            )
            return {
                "total_unique": len(deduped),
                "crawl_id": crawl_id,
                "queries_failed": failed,
            }
        except Exception as e:
            print(
                f"  [warn] PG write failed ({e}); falling back to JSON snapshot",
                file=sys.stderr,
            )
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    snapshot = {
        "date": datetime.date.today().isoformat(),
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_unique": len(deduped),
        # ponytail: hot_now = 星标 Top-40 + 精选赛道项目保底（用户清单里的项目
        # 必须可见 — 此前只在 5k 池里，按星标排不进前 40 就整页不可见）。
        "hot_now": (
            lambda top40: top40
            + [
                r
                for r in deduped
                if r.get("curated") and r["name"] not in {x["name"] for x in top40}
            ]
        )(sorted(deduped, key=lambda r: r.get("stars", 0), reverse=True)[:40]),
        "categories": cat_results,
        # 2026-09：trending 专区数据 — 今日上榜的完整列表（带 stars_today），
        # 前端「趋势」tab 直接消费，不再用 hot_now 兜底。
        "trending": sorted(
            [r for r in deduped if r.get("trending")],
            key=lambda r: -(r.get("stars_today") or 0),
        ),
        # ponytail: stars_today carried over from trending scrape — /api/gain uses this when
        # no PG; previously empty because the field lived only on PG rows, not JSON snapshots.
        "stars_today": {
            r["name"]: r["stars_today"]
            for r in trending
            if r.get("stars_today") is not None
        },
    }
    latest_file = DATA / "latest.json"
    latest_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(f"[crawl] saved → {latest_file} ({len(deduped)} repos, JSON mode)")
    return {"total_unique": len(deduped), "fallback": "json", "queries_failed": failed}


def today():
    """Print today's top picks to terminal. PG first, latest.json fallback."""
    if db._DB_OK:
        try:
            conn = db.connect()
            try:
                hot = db.query_hot_now(conn, limit=15)
                cats = db.query_categories(conn)
            finally:
                conn.close()
            print(f"\n⚡ Lodestone · {datetime.date.today().isoformat()} · PG\n")
            print("🔥 Top 15 Hot Now:")
            for i, r in enumerate(hot, 1):
                print(
                    f"  {i:2}. {r['name']:<42} ⭐ {r['stars']:>6,}  {r.get('lang') or '—'}"
                )
                if r.get("description"):
                    print(f"      {r['description'][:90]}")
            print("\n📂 Categories:")
            for cat in cats:
                print(f"  · {cat['name']:<45} {cat['count']} repos")
            return
        except Exception as e:
            print(
                f"[today] PG read failed ({e}); falling back to latest.json",
                file=sys.stderr,
            )
    latest = DATA / "latest.json"
    if not latest.exists():
        print("[today] no data — run `radar.py crawl`", file=sys.stderr)
        sys.exit(1)
    snap = json.loads(latest.read_text())
    print(f"\n⚡ Lodestone · {snap['date']} · {snap['total_unique']} repos\n")
    print("🔥 Top 15 Hot Now:")
    for i, r in enumerate(snap["hot_now"][:15], 1):
        print(f"  {i:2}. {r['name']:<42} ⭐ {r['stars']:>6,}  {r['lang']}")
        if r["desc"]:
            print(f"      {r['desc'][:90]}")
    print("\n📂 Categories:")
    for cat in snap["categories"]:
        print(f"  · {cat['name']:<35} {cat['count']} repos")


def audit():
    """数据质量审计 — 去重 / 金融过滤 / 来源分布 / AI 相关性抽样。
    供人工或 /loop 定期复查：`./radar.py audit`。"""
    latest = DATA / "latest.json"
    if not latest.exists():
        print("no data/latest.json — run ./radar.py crawl first")
        return
    d = json.loads(latest.read_text())
    all_repos = list(d.get("hot_now", []))
    for c in d.get("categories", []):
        all_repos.extend(c.get("repos", []))

    print(
        f"=== 数据质量审计 · {d.get('fetched_at', '?')} · {len(all_repos)} 条（含跨分类重复计数）"
    )

    # 1) 去重规则：git 完整仓库地址
    keys: dict[str, list[str]] = {}
    for r in all_repos:
        k = normalize_git_url(r.get("url")) or r["name"]
        keys.setdefault(k, []).append(r["name"])
    cross = {k: v for k, v in keys.items() if len(set(v)) > 1}
    print(f"1) 跨条目 URL 重复: {len(cross)} {'✓' if not cross else '✗'}")
    for k, v in list(cross.items())[:10]:
        print(f"   {k} ← {sorted(set(v))}")

    # 2) 金融/交易残留
    fin = sorted({r["name"] for r in all_repos if is_finance_blocked(r)})
    print(f"2) 金融/交易残留: {len(fin)} {'✓' if not fin else '✗'} {fin[:8]}")

    # 3) 来源分布（四个主源 + 辅助源）
    from collections import Counter

    src = Counter(r.get("source", "?") for r in all_repos)
    print("3) 来源分布:")
    for s, n in src.most_common(10):
        print(f"   {s:<28} {n}")

    # 4) GitHub 条目 AI 相关性抽样（5k 池口径的严格过滤在入库时已做；
    #    这里抽样检查分类条目里有没有明显不相关的）
    gh = [r for r in all_repos if normalize_git_url(r.get("url")).startswith("gh://")]
    weak = [
        r["name"]
        for r in gh
        if not is_ai_relevant(r)
        and not any(
            t in AI_TOPIC_BLOCKLIST
            for t in (x.lower() for x in (r.get("topics") or []))
        )
    ]
    # 注：分类条目允许过严格过滤（topics 变体），这里只报告数量供人工抽查
    print(
        f"4) GitHub 条目未过严格 AI 过滤（分类口径允许，供抽查）: {len(weak)}/{len(gh)}"
    )
    for n in weak[:8]:
        print(f"   {n}")

    # 5) 分类规模健康度
    cats = d.get("categories", [])
    tiny = [
        (c["id"], len(c.get("repos", []))) for c in cats if len(c.get("repos", [])) < 5
    ]
    print(f"5) 分类数 {len(cats)} · 过小分类(<5): {tiny or '无 ✓'}")


def fetch_huggingface_trending(max_items: int = 30, sort: str = "likes7d") -> list:
    """HuggingFace Trending Spaces — JSON API (no auth). Returns repo-shaped dicts so the
    rest of the pipeline (translation, upsert, hot_now) works without special-casing.

    ponytail: HF's public API has no literal "trending" sort, but `sort=likes7d` returns
    `trendingScore` (their internal 7-day pop score). We surface that as `stars` so the
    rest of the UI / sorting treats HF spaces uniformly. `likes` becomes total likes (lifetime).

    2026-09: sort 白名单与 sources/huggingface_models.py 共用（两个 HF fetcher
    一套规则），非法值回退 likes7d。

    Source: https://huggingface.co/api/spaces?sort=likes7d&limit=N (public JSON).
    Falls back to system `curl` when Python's SSL certs are missing (macOS Python builds
    commonly lack the cert chain). Returns [] on any error — HF down shouldn't block
    the GitHub crawl."""
    try:
        from sources.huggingface_models import VALID_SORTS
    except Exception:
        VALID_SORTS = ("trending", "likes7d", "downloads", "downloads7d", "updated")
    if sort not in VALID_SORTS:
        print(
            f"  [warn] HF spaces: invalid sort {sort!r}, falling back to likes7d",
            file=sys.stderr,
        )
        sort = "likes7d"
    url = f"https://huggingface.co/api/spaces?sort={sort}&limit={max_items}"
    data = None
    # ponytail: 2026-09 — httpx 优先（自带 certifi 证书链）。本机实测 urllib 100%
    # SSL: CERTIFICATE_VERIFY_FAILED（macOS Python 缺系统证书链），curl 走系统
    # 代理偶发 Connection reset — 两级都塌导致 Spaces 分类连续两次爬到 0 条。
    try:
        import httpx

        r = httpx.get(
            url,
            timeout=20,
            headers={"User-Agent": "lodestone/1.0"},
            follow_redirects=True,
        )
        if r.status_code == 200 and r.text.strip():
            data = r.json()
    except Exception:
        pass
    # ponytail: httpx 已拿到数据就别再走旧路径 — 旧路径 urllib 失败后 curl 再失败
    # 会 return []，把 httpx 的成功结果一起丢掉（Spaces 连续 0 条的根因之二）。
    if data is None:
        # ponytail: try Python urllib first (zero deps)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lodestone/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            # ponytail: macOS Python often lacks system certs — fall back to system `curl`
            # which uses the OS keychain. Public JSON API, no secrets at risk.
            try:
                out = subprocess.run(
                    # ponytail: `-q` skips ~/.curlrc (which appends "HTTP %{http_code}…" that
                    # would break json.loads on the captured stdout). Public API, no auth.
                    [
                        "curl",
                        "-q",
                        "-sS",
                        "--max-time",
                        "20",
                        "-A",
                        "lodestone/1.0",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=25,
                )
                if out.returncode == 0 and out.stdout.strip():
                    data = json.loads(out.stdout)
                else:
                    print(
                        f"  [warn] HF trending (curl) failed: {out.stderr.strip()[:120] or e}",
                        file=sys.stderr,
                    )
                    return []
            except Exception as e2:
                print(
                    f"  [warn] HF trending fetch failed: {e}; curl: {e2}",
                    file=sys.stderr,
                )
                return []
    out = []
    # ponytail: HF API returns a list on success, a dict ({"error": "..."}) on rate-limit
    # / auth errors. Be defensive — only iterate if it's actually a list.
    items = data if isinstance(data, list) else []
    for s in items[:max_items]:
        sid = s.get("id") or ""
        if "/" not in sid:
            continue
        likes = int(s.get("likes") or 0)
        trend = int(s.get("trendingScore") or 0)
        # ponytail: trendingScore is what makes "trending" — surface as stars (UI badge
        # reads "⭐ N") and keep likes in topics as a secondary signal.
        out.append(
            {
                "name": sid,
                "full_name": sid,
                "url": f"https://huggingface.co/spaces/{sid}",
                "description": (s.get("description") or "").strip()[:500],
                "desc": (s.get("description") or "").strip()[:500],
                "stars": trend,  # 7-day trending score (UI displays as ⭐)
                "forks": 0,
                "lang": "python",  # most HF spaces are Gradio/Streamlit on Python
                "topics": ["huggingface", "space", *(s.get("tags") or [])][:6],
                "updated": (s.get("lastModified") or "")[:10],
                "pushed": (s.get("lastModified") or "")[:10],
                "score": trend,
                "best_category": "huggingface",
                "is_ai_relevant": True,  # HF trending is already AI-curated by the community
                "source": "huggingface_trending",
                "hf_likes": likes,  # kept for the drawer
            }
        )
    print(f"  ✓ HuggingFace: {len(out)} trending spaces", file=sys.stderr)
    return out
