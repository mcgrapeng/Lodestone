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
from radar_pkg.progress import phase, bar, eta, log, done
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
from radar_pkg.readme import fetch_and_cache_readmes


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
    """Non-acquiring check for the API layer (returns 409 instead of spawning)。
    ponytail: 2026-09 — lock 文件存在但 mtime 超过 CRAWL_LOCK_STALE_S 时,仍要
    看 lock 里的 PID 还活没活:活就当 held(只是慢,没卡死);死才返 False 让 API
    能重启。旧逻辑只看 mtime,长 README 抓取阶段(>30min 没写 log)会被误判 stale,
    前端 banner 瞬间消失 + 显示 stale 的「trending 6/6 100%」。"""
    if not CRAWL_LOCK.exists():
        return False
    try:
        st_mtime = CRAWL_LOCK.stat().st_mtime
    except OSError:
        return False
    if time.time() - st_mtime <= CRAWL_LOCK_STALE_S:
        return True
    # ponytail: 超 stale 但 PID 还活 → held;死了 → False
    try:
        pid = int(CRAWL_LOCK.read_text().strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def crawl(with_llm: bool = False):
    """Fetch all categories, dedupe, save. File-locked — one crawl at a time.

    with_llm: 2026-09 P3 — 默认 False。LLM 5 桶分析改由 summarize_repos() 手动
    触发（旧行为需要走 ./radar.py crawl --with-llm,服务侧 /api/crawl 仍不自动跑 LLM）。
    """
    if not acquire_crawl_lock():
        print("[crawl] another crawl is already running — aborting", file=sys.stderr)
        return {"ok": False, "error": "crawl already running"}
    try:
        return _crawl_inner(with_llm=with_llm)
    finally:
        release_crawl_lock()


def _run_llm_analysis(repos: list) -> int:
    """对一批 repo 跑 LLM 5 桶分析,把 analysis_5d 写回每个 repo 字典。

    Returns: 成功分析的 repo 数。供 _crawl_inner(with_llm=True) 和 summarize_repos()
    共用 — 增量分析(llm_analysis_cache.json 命中跳过),失败静默,不抛异常打断爬取。

    副作用: 把 analysis_5d 写回 repos[i].analysis_5d 字段(供 PG upsert 落库),
    同步更新 readme_zh_cache.json 里对应 entry 的 analysis_5d 字段。
    """
    from radar_pkg.llm_analyze import analyze_many, _load_cache as _load_llm_cache

    readme_cache: dict = {}
    if core.README_ZH_CACHE.exists():
        try:
            readme_cache = json.loads(core.README_ZH_CACHE.read_text())
        except Exception:
            readme_cache = {}
    llm_inputs = []
    for r in repos:
        name = (r.get("name") or "").lower()
        entry = readme_cache.get(name) or {}
        # 先把已有 analysis_5d 灌回 repo(让前端在跑分析时也能看到旧桶)
        if entry.get("analysis_5d"):
            r["analysis_5d"] = entry["analysis_5d"]
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
    if not llm_inputs:
        return 0
    n = analyze_many(llm_inputs, max_workers=4)
    try:
        llm_cache = _load_llm_cache()
    except Exception:
        llm_cache = {}
    # ponytail: 2026-09 — 一次性 load llm cache（旧代码每 repo 重读磁盘）
    # 把分析结果回写到 readme_zh_cache（共享缓存文件，避免再开一个）。
    # ponytail: 2026-09 P3 修复 — O(N) dict 索引替代 O(N×M) 内嵌 for。
    # 250 个 repo × 250 个输入 = 62.5k 次比较降到 ~250 次（构建 by_name 一次再 O(1) get）。
    by_name_lower = {(r.get("name") or "").lower(): r for r in repos}
    for inp in llm_inputs:
        key = inp["name"].lower()
        if key in llm_cache:
            readme_cache.setdefault(key, {})["analysis_5d"] = llm_cache[key]
            r = by_name_lower.get(key)
            if r is not None:
                r["analysis_5d"] = llm_cache[key]
    try:
        core.atomic_json_write(core.README_ZH_CACHE, readme_cache)
    except Exception as e:
        print(f"  [warn] write analysis_5d back to cache: {e}", file=sys.stderr)
    return n


def _write_llm_status(**fields) -> None:
    """更新 llm_status.json(给 /api/llm/status 读)。原子写。"""
    payload = {}
    if core.LLM_STATUS_PATH.exists():
        try:
            payload = json.loads(core.LLM_STATUS_PATH.read_text())
        except Exception:
            payload = {}
    payload.update(fields)
    payload["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    core.LLM_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = core.LLM_STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    tmp.replace(core.LLM_STATUS_PATH)


def summarize_repos(force: bool = False) -> dict:
    """手动触发 LLM 5 桶分析 — 读取 PG/JSON snapshot 里的 repos,跑 LLM,
    把 analysis_5d 写回 PG + data/latest.json + data/readme_zh_cache.json。

    用法: ./radar.py summarize
    /api/llm/summarize 也会调它（subprocess spawn）。

    Returns: {ok, analyzed, skipped, source, duration_s, error?}
    """
    import db
    from radar_pkg.llm_analyze import detect_provider, _provider_model

    if not acquire_summarize_lock():
        return {"ok": False, "error": "summarize already running"}
    t0 = time.monotonic()
    # ponytail: 2026-09 — 立刻写 running=True + started_at。前端 banner 立刻显示
    # 进度条(哪怕数据 fetch 还在跑或失败);否则用户点完按钮 0.5s 内看不到任何反馈。
    from radar_pkg.llm_analyze import detect_provider as _dp, _provider_model as _pm
    _prov = _dp()
    _started_at = datetime.datetime.now().isoformat(timespec="seconds")
    _write_llm_status(
        running=True,
        current=0,
        total=0,
        analyzed_running=0,
        started_at=_started_at,
        provider=_prov,
        model=_pm(_prov) if _prov else None,
    )
    try:
        provider = _prov
        if not provider:
            _write_llm_status(
                running=False,
                current=None,
                total=None,
                analyzed_running=None,
                started_at=None,
            )
            return {
                "ok": False,
                "error": "no LLM provider configured — open Settings and set provider/api_key/base_url",
            }
        # ponytail: 2026-09 — PG 优先; 没有 PG 或读失败回退到 data/latest.json
        repos: list = []
        source = "json"
        if db._DB_OK:
            try:
                conn = db.connect()
                try:
                    repos = db.query_all_repos_for_summarize(conn)
                finally:
                    conn.close()
                source = "pg"
            except Exception as e:
                print(f"  [warn] summarize PG read failed ({e}); falling back to latest.json",
                      file=sys.stderr)
                repos = []
        if not repos:
            latest = DATA / "latest.json"
            if not latest.exists():
                # ponytail: 2026-09 — 清掉 running 状态,前端 banner 切到 done/失败态。
                _write_llm_status(
                    running=False,
                    current=None,
                    total=None,
                    analyzed_running=None,
                    started_at=None,
                )
                return {"ok": False, "error": "no data — run ./radar.py crawl first"}
            snap = json.loads(latest.read_text())
            for r in snap.get("hot_now", []):
                repos.append(r)
            for c in snap.get("categories", []):
                repos.extend(c.get("repos", []))
            source = "json"
        # ponytail: 2026-09 — 去重(同一 repo 跨多个 category 进来会重复算 LLM 配额)
        seen = set()
        unique = []
        for r in repos:
            n = (r.get("name") or "").lower()
            if not n or "/" not in n:
                continue
            if n in seen:
                continue
            seen.add(n)
            unique.append(r)
        print(
            f"[summarize] source={source} provider={provider} model={_provider_model(provider)} "
            f"repos={len(unique)}"
        )
        # analyze_one 内部跳过 stars < threshold,所以 unique 全喂即可
        n = _run_llm_analysis(unique)
        # 写回存储
        if source == "pg":
            try:
                _write_analysis_to_pg(unique)
            except Exception as e:
                print(f"  [warn] write analysis_5d to PG: {e}", file=sys.stderr)
        _write_analysis_to_snapshot(unique)
        # _run_llm_analysis 已经把 analysis_5d 写回 readme_zh_cache.json 了
        duration = round(time.monotonic() - t0, 1)
        # ponytail: 2026-09 P4 修复 — SIGKILL 兜底清理。如果 subprocess 被 kill -9,
        # analyze_many() 里 try/finally 不会跑,llm_status.json 残留 running=True +
        # analyzed_running=last_value,前端 banner 显示「上次跑的中间状态」。
        # 注册 atexit 钩子 + SIGTERM/SIGINT 处理器,任何非自然退出都会清掉。
        def _cleanup_running_state():
            try:
                _write_llm_status(
                    running=False,
                    current=None,
                    analyzed_running=None,
                    started_at=None,
                )
            except Exception:
                pass
        import atexit as _atexit, signal as _signal
        _atexit.register(_cleanup_running_state)
        def _handler(signum, frame):
            _cleanup_running_state()
            import sys as _sys
            _sys.exit(128 + signum)
        for _sig in (_signal.SIGTERM, _signal.SIGINT):
            try:
                _signal.signal(_sig, _handler)
            except (ValueError, OSError):
                pass  # 某些环境(如主线程之外的线程)不让改 signal
        _write_llm_status(
            last_run_at=datetime.datetime.now().isoformat(timespec="seconds"),
            running=False,  # ponytail: 2026-09 — 跑完清掉 running + 进度,前端知道跑完了
            current=None,
            total=len(unique),
            analyzed_running=None,
            analyzed=n,
            source=source,
            provider=provider,
            model=_provider_model(provider),
            duration_s=duration,
        )
        print(f"[summarize] ✓ {n}/{len(unique)} repos got 5d analysis in {duration}s")
        return {
            "ok": True,
            "analyzed": n,
            "total": len(unique),
            "source": source,
            "duration_s": duration,
        }
    finally:
        release_summarize_lock()


def acquire_summarize_lock() -> bool:
    """True = acquired (caller must release); False = another summarize is running."""
    try:
        fd = os.open(core.SUMMARIZE_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            if time.time() - core.SUMMARIZE_LOCK.stat().st_mtime > core.SUMMARIZE_LOCK_STALE_S:
                core.SUMMARIZE_LOCK.unlink(missing_ok=True)
                return acquire_summarize_lock()
        except OSError:
            pass
        return False


def release_summarize_lock():
    core.SUMMARIZE_LOCK.unlink(missing_ok=True)


def summarize_lock_held() -> bool:
    """Non-acquiring check for the API layer (returns 409 instead of spawning)。
    ponytail: 2026-09 — 与 crawl_lock_held 对齐:lock mtime 超 stale 但 PID 还活,
    视为 held(慢但没卡死);PID 死了才 False。避免 kill -9 后 30min 内 /api/llm/summarize
    永远 409。"""
    if not core.SUMMARIZE_LOCK.exists():
        return False
    try:
        st_mtime = core.SUMMARIZE_LOCK.stat().st_mtime
    except OSError:
        return False
    if time.time() - st_mtime <= core.SUMMARIZE_LOCK_STALE_S:
        return True
    # mtime 超 stale — 检查 PID
    try:
        pid = int(core.SUMMARIZE_LOCK.read_text().strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _write_analysis_to_pg(repos: list) -> None:
    """把 analysis_5d 写回 PG repos.analysis_5d_json 列。"""
    import db

    conn = db.connect()
    try:
        cur = conn.cursor()
        # batch update — 只写有 analysis_5d 的行(空 dict 跳过)
        rows = [
            (json.dumps(r["analysis_5d"]), r["name"])
            for r in repos
            if r.get("analysis_5d")
        ]
        if not rows:
            return
        cur.executemany(
            "UPDATE repos SET analysis_5d_json = %s::jsonb WHERE name = %s",
            rows,
        )
        conn.commit()
        print(f"  ✓ wrote analysis_5d to PG for {len(rows)} repos")
    finally:
        conn.close()


def _write_analysis_to_snapshot(repos: list) -> None:
    """把 analysis_5d 写回 data/latest.json 的每个 repo 条目。"""
    latest = DATA / "latest.json"
    if not latest.exists():
        return
    snap = json.loads(latest.read_text())
    by_name = {(r.get("name") or "").lower(): r for r in repos if r.get("analysis_5d")}
    if not by_name:
        return
    n_updated = 0
    for bucket_key in ("hot_now", "trending"):
        for r in snap.get(bucket_key, []) or []:
            key = (r.get("name") or "").lower()
            if key in by_name:
                r["analysis_5d"] = by_name[key]["analysis_5d"]
                n_updated += 1
    for c in snap.get("categories", []) or []:
        for r in c.get("repos", []) or []:
            key = (r.get("name") or "").lower()
            if key in by_name:
                r["analysis_5d"] = by_name[key]["analysis_5d"]
                n_updated += 1
    tmp = latest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snap, ensure_ascii=False, indent=2))
    tmp.replace(latest)
    print(f"  ✓ wrote analysis_5d to latest.json for {n_updated} repo entries")


def _crawl_inner(with_llm: bool = False):
    """Fetch all categories, dedupe, save.

    with_llm: 默认 False — 不再随 crawl 自动跑 LLM(2026-09 P3 拆分)。
    用户配好模型后通过 ./radar.py summarize 或前端按钮手动触发。
    需要旧行为的 CLI: ./radar.py crawl --with-llm
    """
    today = datetime.date.today().isoformat()
    core.GH_SEARCH_STATS["failed"] = 0
    # ponytail: 2026-09 — 重置自适应限速 sleep。REST 限流恢复把 sleep 永久 bump 到 6.0
    # (gh.py:53),不重置会让后续 crawl 在同进程内一直慢到下次重启。
    core._SEARCH_PACE["sleep"] = 2.0
    _t_crawl = time.monotonic()
    log(f"[crawl] {today} — {len(CATEGORIES)} categories")
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

        phase(f"GraphQL batch · {_all_gh_queries.__len__()} cats + {len(TOP_5K_QUERIES)} 5k + new-star")
        _t_gql = time.monotonic()
        log(f"  → cats ({len(_all_gh_queries)} queries)…")
        _batch.update(gh_search_batch(_all_gh_queries, per_page=30, batch_size=6))
        bar("cats", 1, 3)
        log(f"  → 5k ({len(TOP_5K_QUERIES)} queries)…")
        _batch.update(
            gh_search_batch(
                TOP_5K_QUERIES, per_page=50, batch_size=8, follow_page2=True
            )
        )
        bar("5k", 2, 3)
        # ponytail: 2026-09 P1 修复 — 低星新星通道。全部 5k 池查询 stars:>500、
        # 分类查询大多 stars:>100+，"刚开源、<500 星、没上 trending"的项目有
        # 真空期（实测 PG 中 stars<500 且无分类的行 = 0）。近 14 天 created +
        # 硬 topic + stars:>50 专门捞这批；走独立通道并入（不参与星标截断）。
        log("  → new-star (recent low-star AI)…")
        _new_star_queries = [
            f"stars:>50 created:>{_new_star_cutoff} topic:{t}"
            for t in ("llm", "ai-agent", "mcp-server", "claude-code", "ai-coding")
        ]
        _batch.update(gh_search_batch(_new_star_queries, per_page=30, batch_size=6))
        bar("new-star", 3, 3)
        done(f"GraphQL done{eta(_t_gql, 3, 3)}")
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

    phase(f"Category fetch · {len(CATEGORIES)} categories")
    _t_cats = time.monotonic()
    for ci, cat in enumerate(CATEGORIES, 1):
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
        print(f"  ✓ {cat['name']}: {len(repos)} repos", flush=True)
        bar("cats", ci, len(CATEGORIES), width=32)
    done(f"categories done{eta(_t_cats, len(CATEGORIES), len(CATEGORIES))}")

    # ponytail: 5k+ pass — catch mainstream AI tools not matched by category queries
    phase(f"5k+ pass · {len(TOP_5K_QUERIES)} queries")
    _t_5k = time.monotonic()
    # ponytail: 2026-09 P2 — 池内合并键统一小写:GitHub full_name 大小写随改名
    # 变化,精确比较会产生大小写变体漏合并(单次 crawl 内 normalize_git_url 已
    # 小写,这里对齐同一语义;repo["name"] 原样保留供显示)。
    top_5k_repos = {}
    for qi, q in enumerate(TOP_5K_QUERIES, 1):
        try:
            for r in _query_repos(q, per_page=100):
                if not is_ai_relevant(r):
                    continue
                top_5k_repos.setdefault(r["name"].lower(), r)
        except Exception as e:
            print(f"  [warn] 5k+ query '{q}' failed: {e}", flush=True)
        if qi % 5 == 0 or qi == len(TOP_5K_QUERIES):
            bar("5k queries", qi, len(TOP_5K_QUERIES), width=32)

    print(
        f"  ✓ 5k+ pass: {len(top_5k_repos)} repos after AI filter "
        f"(search phase {time.monotonic() - _search_t0:.0f}s)",
        flush=True,
    )
    done(f"5k+ pass done{eta(_t_5k, len(TOP_5K_QUERIES), len(TOP_5K_QUERIES))}")

    # ponytail: manual seed — guaranteed inclusion of well-known AI tools that escape topic search
    phase(f"Manual seed · {len(MANUAL_SEED_REPOS)} repos")
    si = 0
    for full_name in MANUAL_SEED_REPOS:
        si += 1
        if full_name.lower() in top_5k_repos:
            bar("seed", si, len(MANUAL_SEED_REPOS), width=32)
            continue
        r = gh_fetch_repo(full_name)
        if not r or not is_ai_relevant(r):
            bar("seed", si, len(MANUAL_SEED_REPOS), width=32)
            continue
        top_5k_repos[full_name.lower()] = r
        print(f"  ✓ manual seed: {full_name} ({r['stars']} ⭐)", flush=True)
        bar("seed", si, len(MANUAL_SEED_REPOS), width=32)
    done(f"manual seed done{eta(_t_crawl, max(si, 1), max(len(MANUAL_SEED_REPOS), 1))}")

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
    phase(f"Trending · {len(_trend_routes)} routes (daily/weekly × all-lang + python/ts/rust/go)")
    _t_trend = time.monotonic()
    print(
        f"[crawl] GitHub trending ({len(_trend_routes)} routes: daily/weekly × all-lang + python/ts/rust/go)…",
        flush=True,
    )
    trending_daily, trending_weekly, _trend_lang = [], [], []
    with ThreadPoolExecutor(max_workers=len(_trend_routes)) as _tex:
        _futs = {
            _tex.submit(fetch_github_trending, since, 30, lang): (since, lang)
            for since, lang in _trend_routes
        }
        for ti, (_fut, (_since, _lang)) in enumerate(_futs.items(), 1):
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
            bar("trending routes", ti, len(_trend_routes), width=32)
    done(f"trending done{eta(_t_trend, len(_trend_routes), len(_trend_routes))}")
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
    # ponytail: keep trending SEPARATELY so the 800-row TOP_5K_LIMIT truncation below can't
    # drop their stars_today. Trending repos are low-star by definition (the whole point is
    # "new today" / "rising this week") — they'd otherwise be at the bottom of the 800-row slice.
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

    for r in deduped:
        r["facts"] = facts_for_repo(r)
        r["local_installed"] = (
            r["name"].lower() in installed_segs
            or r["name"].split("/")[-1].lower() in installed_segs
        )
        # 精选赛道标记 — hot_now 保底浮出用（CURATED_ALLOWLIST + 手工种子）
        r["curated"] = (r["name"].lower() in CURATED_ALLOWLIST) or (
            r["name"] in MANUAL_SEED_REPOS
        )

    # ponytail: 2026-09 — 谷歌翻译管线已移除（本网络不可达，白烧 12 分钟超时）。
    # 现在只抓 README 存 raw_md 缓存（llm_analyze 备料）+ 本地 topic 匹配
    # competitive 桶；中文 5 桶由宿主 LLM /api/save_summary_batch 回写。
    try:
        phase(f"README cache · {len(deduped)} repos")
        _t_rm = time.monotonic()
        n_readme = fetch_and_cache_readmes(deduped)
        done(f"readme cached: {n_readme}/{len(deduped)} entries{eta(_t_rm, len(deduped), len(deduped))}")
    except Exception as e:
        print(f"  [warn] readme fetch failed: {e}", file=sys.stderr)

    # ponytail: 2026-09 — LLM 5 维度决策分析（什么 / 痛点 / 竞品 / 优缺 / 何时选）。
    # 2026-09 P3 拆分:不再随 crawl 自动跑,改由 summarize_repos() 手动触发。
    # 仅在配置 ANTHROPIC_API_KEY / OPENAI_API_KEY / OLLAMA_HOST 时启用；否则降级
    # 到 summary_sections 三桶 README 摘要。增量分析 — cache 命中跳过。
    if with_llm:
        try:
            _run_llm_analysis(deduped)
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
                f"[crawl] saved → postgres ai_radar ({n_inserted} added, {n_updated} updated, {len(deduped)} unique this run)",
                flush=True,
            )
            done(f"crawl done — {time.monotonic()-_t_crawl:.0f}s total")
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
    core.atomic_json_write(latest_file, snapshot)
    print(f"[crawl] saved → {latest_file} ({len(deduped)} repos, JSON mode)", flush=True)
    done(f"crawl done — {time.monotonic()-_t_crawl:.0f}s total")
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
