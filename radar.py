#!/usr/bin/env python3
"""
lodestone: GitHub AI trending crawler + JSON API for the Vue 3 frontend.

Commands:
  radar.py crawl          - fetch trending AI repos from GitHub, write to PG (fallback: data/latest.json)
                            2026-09 P3: 不再自动跑 LLM,需要走 --with-llm 显式打开
  radar.py crawl --with-llm  - 同上,顺带跑 5 桶 LLM 分析(走已配好的 provider)
  radar.py summarize      - 单独跑 LLM 5 桶分析(读 PG/JSON 已有 repos,跑已配好的 provider)
                            /api/llm/summarize 与前端 Settings 按钮都调它
  radar.py serve          - JSON API on http://localhost:PORT (loopback only; Vite at :5173 proxies /api/* here)
  radar.py web            - one-shot dashboard: start serve in background (if needed) + open browser
  radar.py today          - print today's top picks in terminal

Reuses `gh` CLI for GitHub auth (avoids token management).
Ponytail: minimum code, stdlib only, Vue UI lives in frontend/.
"""

import json
import subprocess
import argparse
import sys
import os
import re
import datetime
import time
import http.server
import socketserver
import urllib.request
import urllib.parse
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import db  # ponytail: PG is source of truth (was: data/latest.json)


# ponytail: 2026-09 架构拆分 — radar.py 是薄 facade,实现在 radar_pkg/
from radar_pkg.core import (  # noqa: F401
    ROOT,
    DATA,
    SKILLS_CACHE,
    SKILL_ORIGINS,
    README_ZH_CACHE,
    CATEGORIES,
    TOP_5K_QUERIES,
    TOP_5K_LIMIT,
    AI_TOPIC_HARD,
    AI_TEXT_HINTS,
    CURATED_ALLOWLIST,
    AI_TOPIC_BLOCKLIST,
    NON_AI_DEV_DESC_BLOCKLIST,
    _SEARCH_PACE,
    GH_SEARCH_STATS,
    CRAWL_LOCK,
    CRAWL_LOCK_STALE_S,
    FRONTMATTER_DESC,
    MANUAL_SEED_REPOS,
    is_finance_blocked,
    is_ai_relevant,
    normalize_git_url,
    facts_for_repo,
    _parse_frontmatter_desc,
    _repo_slug_from_url,
)
from radar_pkg.match import (  # noqa: F401
    _owner_repo_from_url,
    _owner_repo_from_link_target,
    _load_repo_index,
    _repo_index_cache,
    _REPO_INDEX_TTL,
    invalidate_repo_index,
    _installed_segments,
    _annotate_local_installed,
    _build_plugin_segs,
    _per_cli_installed_map,
)
from radar_pkg.detect import (  # noqa: F401
    _SKILL_PLATFORM_PATHS,
    SKILL_PLATFORM_LABELS,
    SUPPORTED_CLIS,
    KNOWN_CLIS,
    _skills_root_for,
    _LOCAL_SCAN_TTL,
    _local_scan_cache,
    _local_scan_lock,
    invalidate_local_scan,
    detect_local_skills,
    detect_cli_tools,
)
from radar_pkg.gh import (  # noqa: F401
    _search_pace,
    _gh_repo_meta,
    gh_search,
    _parse_github_search_html,
    _gh_search_html_fallback,
    gh_fetch_repo,
    fetch_github_trending,
    fetch_recent_active_repos,
)
from radar_pkg.readme import (  # noqa: F401
    _attach_competitive,
    _fetch_readme_from_github,
    fetch_and_cache_readmes,
)
from radar_pkg.install import (  # noqa: F401
    _GENERIC_TOPICS,
    _git_head_sha,
    _git_pull_fast_forward,
    _git_remote_head_sha,
    install_skill_from_github,
    uninstall_skill,
    replace_skill,
    find_skill_replacements,
    set_capability_origin,
    group_capabilities_by_origin,
    install_cli_wrapper,
)
from radar_pkg.crawl import (  # noqa: F401
    acquire_crawl_lock,
    release_crawl_lock,
    crawl_lock_held,
    crawl,
    _crawl_inner,
    today,
    audit,
    fetch_huggingface_trending,
)
from radar_pkg.serve import (  # noqa: F401
    serve,
    web,
)

# 共享可变常量经定义模块属性访问(patch 穿透);值绑定 re-export 仅供外部读取兼容
from radar_pkg import core as _core, detect as _detect  # noqa: E402
GH_SEARCH_STATS = _core.GH_SEARCH_STATS
README_ZH_CACHE = _core.README_ZH_CACHE
SKILLS_CACHE = _core.SKILLS_CACHE
SKILL_ORIGINS = _core.SKILL_ORIGINS
_SEARCH_PACE = _core._SEARCH_PACE
_SKILL_PLATFORM_PATHS = _detect._SKILL_PLATFORM_PATHS


def _parse_port() -> int:
    """共用:解析 `radar.py serve 8765` / `restart 8766` 的可选端口参数。"""
    parser = argparse.ArgumentParser(prog="radar.py", add_help=False)
    parser.add_argument("port", nargs="?", type=int, default=8765)
    return parser.parse_known_args(sys.argv[2:])[0].port


if __name__ == "__main__":
    # ponytail: 2026-09 — load project .env once at entry so every command
    # (crawl/serve/web/today/audit) sees GH_TOKEN / FIRECRAWL_API_KEY /
    # ANTHROPIC_API_KEY etc. Shell env wins (setdefault semantics in env_loader).
    from env_loader import load_env
    load_env()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "today"
    if cmd == "crawl":
        # ponytail: 2026-09 P3 — LLM 不再随 crawl 自动跑。需要旧行为的:
        # `./radar.py crawl --with-llm`；正常用法 `./radar.py crawl` 只拉数据。
        from radar_pkg.crawl import crawl as _crawl
        _crawl(with_llm=("--with-llm" in sys.argv))
    elif cmd == "serve":
        serve(_parse_port())
    elif cmd == "restart":
        # ponytail: 2026-09 — 独立 CLI 子命令,做 kill 旧 + spawn 新 + wait alive,
        # 与 /yz:ai skill 配合(/api/restart 调用此命令).
        # 独立进程避免 fork+inherit 父 serve 监听 socket 的复杂性.
        from radar_pkg.serve import _restart_serve
        port = _parse_port()
        try:
            result = _restart_serve(port)
            print(f"[restart] OK: {result}", flush=True)
            sys.exit(0)
        except Exception as e:
            print(f"[restart] FAILED: {e}", file=sys.stderr, flush=True)
            sys.exit(1)
    elif cmd == "summarize":
        # ponytail: 2026-09 P3 — 手动跑 LLM 5 桶分析。/api/llm/summarize 也调它。
        # 配置好模型后 ./radar.py summarize 或前端 Settings 抽屉按钮触发。
        from radar_pkg.crawl import summarize_repos
        result = summarize_repos()
        if not result.get("ok"):
            print(f"[summarize] FAIL: {result.get('error')}", file=sys.stderr, flush=True)
            sys.exit(1)
        sys.exit(0)
    elif cmd == "web":
        _port = _parse_port()
        web(_port)
    elif cmd == "today":
        today()
    elif cmd == "audit":
        audit()
    elif cmd == "upgrade_all":
        # ponytail: 2026-09 — 批量升级 CLI 子命令,/api/upgrade-all 触发。
        # 串行跑 ls-remote + fetch,慢但不爆炸 GitHub rate limit。
        # ponytail: 2026-09 P3 修复 — 接收 --upgradable JSON 参数(handler 算过,
        # 避免 subprocess 自己再算一遍导致 total 闪烁)。用 argparse 替代手写
        # sys.argv 循环(原实现 _ua(..., upgradable=...) LSP 不识别,因为
        # import 在分支内 lazy,静态分析器看不到签名)。
        import json as _json
        from radar_pkg.detect import detect_local_skills
        from radar_pkg.install import upgrade_all as _ua
        parser = argparse.ArgumentParser(prog="radar.py upgrade_all")
        parser.add_argument(
            "--upgradable",
            type=_json.loads,
            default=None,
            help="JSON dict from /api/local upgradable field; if omitted, computes locally",
        )
        ua_args = parser.parse_args(sys.argv[2:])
        local = detect_local_skills()
        result = _ua(local.get("skills") or {}, upgradable=ua_args.upgradable)
        # ponytail: 2026-09 — 字段名是 upgradable(不是 upgraded),与 upgrade_all return dict 对齐。
        # 之前 typo 在新加的 try/finally BaseException 路径下被显形(error 路径返 upgradable=0)。
        if result.get("error"):
            print(f"[upgrade_all] FAIL: {result['error']}", file=sys.stderr, flush=True)
            sys.exit(1)
        print(
            f"[upgrade_all] upgradable={result.get('upgradable', 0)} "
            f"skipped={result.get('skipped', 0)} "
            f"failed={result.get('failed', 0)} total={result.get('total', 0)}",
            flush=True,
        )
        sys.exit(0)
    else:
        print(__doc__)
        sys.exit(1)
