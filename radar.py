#!/usr/bin/env python3
"""
lodestone: GitHub AI trending crawler + JSON API for the Vue 3 frontend.

Commands:
  radar.py crawl   - fetch trending AI repos from GitHub, write to PG (fallback: data/latest.json)
  radar.py serve   - JSON API on http://localhost:PORT (loopback only; Vite at :5173 proxies /api/* here)
  radar.py web     - one-shot dashboard: start serve in background (if needed) + open browser
  radar.py today   - print today's top picks in terminal

Reuses `gh` CLI for GitHub auth (avoids token management).
Ponytail: minimum code, stdlib only, Vue UI lives in frontend/.
"""

import json
import subprocess
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
    TRANSLATE_CACHE,
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
from radar_pkg.translate import (  # noqa: F401
    _LANG_NAV_WORDS,
    _clean_readme_text,
    _summary_from_entry,
    _build_summary_zh,
    enrich_summaries,
    translate_text,
    translate_batch,
    _fetch_readme_from_github,
    _strip_markdown_to_text,
    _chunked_translate,
    _looks_translated,
    get_readme_zh,
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
TRANSLATE_CACHE = _core.TRANSLATE_CACHE
_SEARCH_PACE = _core._SEARCH_PACE
_SKILL_PLATFORM_PATHS = _detect._SKILL_PLATFORM_PATHS


if __name__ == "__main__":
    # ponytail: 2026-09 — load project .env once at entry so every command
    # (crawl/serve/web/today/audit) sees GH_TOKEN / FIRECRAWL_API_KEY /
    # ANTHROPIC_API_KEY etc. Shell env wins (setdefault semantics in env_loader).
    from env_loader import load_env
    load_env()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "today"
    if cmd == "crawl":
        crawl()
    elif cmd == "serve":
        serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    elif cmd == "web":
        web(int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    elif cmd == "today":
        today()
    elif cmd == "audit":
        audit()
    else:
        print(__doc__)
        sys.exit(1)
