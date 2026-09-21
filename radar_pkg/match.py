# -*- coding: utf-8 -*-
"""radar_pkg.match — 已装匹配纯函数(origin 还原/segments/annotate/repo 索引)。
只消费 detect 输出的 dict,不 import detect(依赖无环规约)。"""
import json
import re
import threading
import time
from pathlib import Path

from radar_pkg import core

"""radar_pkg.match — 由 radar.py 搬移(2026-09 架构拆分)。"""
def _owner_repo_from_url(url: str) -> str | None:
    """https://github.com/owner/repo(.git)/… → 'owner/repo';否则 None。"""
    if not url:
        return None
    from urllib.parse import urlparse

    if "github.com" not in (urlparse(url).netloc or ""):
        return None
    parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if owner and repo:
        return f"{owner}/{repo}"
    return None

def _owner_repo_from_link_target(link: Path) -> str | None:
    """本工具安装的 symlink 指向 core.SKILLS_CACHE/owner__repo → 'owner/repo'。
    只认缓存目录前缀,不解析任意链接目标。"""
    try:
        target = link.resolve()
        if core.SKILLS_CACHE.resolve() not in target.parents:
            return None
        stem = target.name  # owner__repo
        if "__" not in stem:
            return None
        owner, _, repo = stem.partition("__")
        if not owner or not repo:
            return None
        if not all(c.isalnum() or c in "-_." for c in owner + repo):
            return None
        return f"{owner}/{repo}"
    except (OSError, RuntimeError):
        return None

def _load_repo_index() -> dict:
    """Build repo lookup {segment → repo} from PG. Used for topic/stars enrichment + replacement detection.
    ponytail: cache 30s — /api/local calls this twice per request, with 30s SPA polling the
    SQL hit becomes ~4x per minute for nothing. Mutations (install/uninstall) call
    invalidate_repo_index() to bust the cache immediately."""
    now = time.time()
    cache = _repo_index_cache
    if cache["data"] is not None and now - cache["ts"] < _REPO_INDEX_TTL:
        return cache["data"]
    by_repo = {}
    try:
        import db

        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT name, url, description, desc_zh, stars, lang, topics, pushed_at, best_category
                FROM repos WHERE is_ai_relevant
            """)
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                rec["topics"] = list(rec.get("topics") or [])
                by_repo[rec["name"].split("/")[-1].lower()] = rec
    except Exception:
        pass
    cache["ts"] = now
    cache["data"] = by_repo
    return by_repo

_repo_index_cache: dict = {"ts": 0.0, "data": None}

_REPO_INDEX_TTL = 30

def invalidate_repo_index():
    _repo_index_cache["ts"] = 0.0
    _repo_index_cache["data"] = None

def _installed_segments(local: dict) -> set:
    """Flatten detect_local_skills() output to a set of FULL owner/repo names.
    ponytail: use full names only — bare segments like "skills" cause false positives.
    Sources:
      0. local skills 目录 origin — meta.url(PG 索引/sidecar)或 origin_full
         (symlink 目标 core.SKILLS_CACHE/owner__repo 还原)。2026-09 修复:此前 skills
         目录完全不参与本函数,凡以技能(非插件)形式装的卡片永远标不出「已装」。
      1. plugin cache .git/config origin (when plugin was git-installed, e.g. obra/superpowers)
      2. plugin's marketplace source repo (when plugin lives in the marketplace repo,
         source is './' relative to marketplace — use marketplace URL as the source)
      3. known_marketplaces.json (covers the marketplace URL itself)
    """
    segs = set()

    # ponytail: 2026-09 — skills 目录 origin(三路:origin_full > url > 跳过)
    for _name, meta in (local.get("skills") or {}).items():
        full = (meta or {}).get("origin_full") or _owner_repo_from_url(
            (meta or {}).get("url") or ""
        )
        if full:
            segs.add(full)

    # ponytail: load marketplace source map once
    mp_source: dict[str, str] = {}
    known_mp = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
    if known_mp.exists():
        try:
            mp_data = json.loads(known_mp.read_text())
            for mp_name, info in (mp_data or {}).items():
                src = info.get("source") or {}
                repo = ""
                if src.get("source") == "github" and src.get("repo"):
                    repo = src["repo"]
                elif src.get("source") == "git" and src.get("url"):
                    u = src["url"].rstrip("/")
                    if u.endswith(".git"):
                        u = u[:-4]
                    repo = u.replace("https://github.com/", "").rstrip("/")
                if repo:
                    mp_source[mp_name] = repo
                    segs.add(repo)
        except (OSError, ValueError):
            pass

    # ponytail: each plugin's effective source repo = cache .git/config origin OR its marketplace URL
    for p in local.get("plugins") or []:
        mp_name = p.get("marketplace", "")
        ip = Path(p.get("install_path", ""))
        git_origin = None
        gc = ip / ".git" / "config"
        if gc.exists():
            try:
                for line in gc.read_text().splitlines():
                    m = re.match(
                        r"\s*url\s*=\s*(https?://github\.com/[^/]+/[^/]+?)(?:\.git)?\s*$",
                        line,
                    )
                    if m:
                        git_origin = (
                            m.group(1).replace("https://github.com/", "").rstrip("/")
                        )
                        break
            except OSError:
                pass
        if git_origin:
            segs.add(git_origin)
        elif mp_name in mp_source:
            segs.add(mp_source[mp_name])
    return segs

def _per_cli_installed_map(local: dict) -> dict:
    """Build {owner/repo_lower: {claude, codex, opencode, easycode}} from detect_local_skills() output.
    Keys are lowercased owner/repo (origin_full preferred, else url → owner/repo). Each CLI
    flag mirrors the boolean in local['skills'][name][<cli>]. Skills without origin contribute
    nothing — they aren't matched to a GitHub repo here.
    """
    out: dict = {}
    for _name, meta in (local.get("skills") or {}).items():
        full = (meta or {}).get("origin_full") or _owner_repo_from_url(
            (meta or {}).get("url") or ""
        )
        if not full:
            continue
        out[full.lower()] = {
            "claude": bool(meta.get("claude", False)),
            "codex": bool(meta.get("codex", False)),
            "opencode": bool(meta.get("opencode", False)),
            "easycode": bool(meta.get("easycode", False)),
        }
    return out


def _annotate_local_installed(rows, installed_segments: set, plugin_segs: "set | None" = None, per_cli_map: "dict | None" = None):
    """Single-pass walk: list → recurse; dict with 'repos' → descend; dict with 'name' → annotate leaf.
    ponytail: category dicts have BOTH `name` AND `repos`, so a `name`-first check would
    annotate the container instead of descending. Prefer the structural `repos` branch.
    ponytail: `plugin_segs` adds bare plugin-name segs (e.g. "ecc", "superpowers") so we
    match GitHub hot_now like `affaan-m/ECC` against the installed ecc plugin.
    ponytail: 2026-09 FU-1.1 — `per_cli_map` (output of `_per_cli_installed_map`) adds the
    4 per-CLI flags RepoCard needs for the "installed on: [claude][codex][opencode][easycode]"
    dot strip. All 4 default to False if the repo isn't in the map (covers hot_now rows for
    repos no one has installed).
    """
    if isinstance(rows, list):
        for r in rows:
            _annotate_local_installed(r, installed_segments, plugin_segs, per_cli_map)
    elif isinstance(rows, dict):
        if "repos" in rows:
            _annotate_local_installed(rows["repos"], installed_segments, plugin_segs, per_cli_map)
        elif "name" in rows:
            full_lower = {s.lower() for s in installed_segments if "/" in s}
            name_lower = rows["name"].lower()
            seg_only = name_lower.split("/")[-1]
            seg_match = plugin_segs is not None and seg_only in plugin_segs
            rows["local_installed"] = name_lower in full_lower or seg_match
            if per_cli_map is not None:
                flags = per_cli_map.get(name_lower) or {}
                rows["local_installed_claude"] = bool(flags.get("claude", False))
                rows["local_installed_codex"] = bool(flags.get("codex", False))
                rows["local_installed_opencode"] = bool(flags.get("opencode", False))
                rows["local_installed_easycode"] = bool(flags.get("easycode", False))

def _build_plugin_segs(local: dict) -> set:
    """Return bare plugin-name segs (e.g. 'ecc', 'superpowers') for hot_now seg matching.
    ponytail: plugin-name segs are specific enough (each Claude plugin has a unique name)
    that they don't need blacklist filtering — unlike 'skills' which would collide.
    """
    return {
        p["name"].split("@")[0].lower()
        for p in (local.get("plugins") or [])
        if p.get("name")
    }
