# -*- coding: utf-8 -*-
"""MCP Server Registry fetcher — pulls official Model Context Protocol servers
from registry.modelcontextprotocol.io. Public JSON API, no auth required.

Endpoint: GET https://registry.modelcontextprotocol.io/v0/servers
   cursor-based pagination via `?cursor=<nextCursor>` (server name + version).
   Returns:
     {
       "servers": [
         {
           "server": {
             "name": "ai.example/mcp-server",
             "title": "Example MCP Server",
             "description": "...",
             "version": "1.0.0",
             "repository": {"url": "https://github.com/...", "source": "github"},
             "websiteUrl": "https://...",
             "remotes": [{"type": "streamable-http", "url": "https://..."}],
             "packages": [{"registryType": "npm", "identifier": "@x/y", ...}],
             "_meta": {
               "io.modelcontextprotocol.registry/official": {
                 "status": "active" | "deprecated",
                 "publishedAt": "...",
                 "updatedAt": "..."
               }
             }
         },
         ...
       ],
       "metadata": {"nextCursor": "...", "count": N}
     }

Strategy:
  - Filter to latest server version per (server name)
  - Filter status="active"
  - Extract GitHub owner/repo when repository.source == "github" → use as name/url
  - When no GitHub repo → fall back to server.name (e.g. "ai.example/mcp") as the
    pseudo "repo name". This keeps registry-only servers discoverable.
  - trendingScore = likes-equivalent: based on the registry is not provided, so we
    surface `updatedAt` recency as the secondary sort. The UI already maps "stars"
    to a ⭐ badge; freshness via updatedAt drives the sort.

Returns list of repo-shaped dicts compatible with the rest of the pipeline
(translation, upsert, hot_now).
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import Optional


REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
PAGE_SIZE = 100  # registry default page size; larger pulls cost a single roundtrip
MAX_PAGES = 8   # ~800 servers; safe upper bound for a single crawl


def _http_get_json(url: str, timeout: int = 30) -> Optional[dict]:
    """Fetch JSON via urllib, falling back to system curl (macOS Python SSL cert fix)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lodestone/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["curl", "-q", "-sS", "--max-time", str(timeout), "-A", "lodestone/1.0", url],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
        return None
    except Exception:
        return None


def _parse_github_repo(repo_url: Optional[str]) -> Optional[tuple[str, str]]:
    """Extract (owner, repo) from a GitHub URL. Returns None for non-github repos
    (gitlab, bitbucket, custom). Tolerates /owner/repo, /owner/repo.git,
    /owner/repo/tree/main/..., /owner/repo/blob/.../file."""
    if not repo_url:
        return None
    try:
        u = urllib.parse.urlparse(repo_url)
    except Exception:
        return None
    if u.netloc.lower() not in ("github.com", "www.github.com"):
        return None
    parts = [p for p in u.path.split("/") if p]
    # ponytail: need at least owner+name; deeper segments (tree/, blob/) are stripped
    # below. .git suffix is also stripped.
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if owner and repo:
        return owner, repo
    return None


def _meta_of(server: dict, entry: Optional[dict] = None) -> dict:
    """Look up _meta.io.modelcontextprotocol.registry/official.
    The real layout (registry v0): the meta block lives at the OUTER entry,
    not inside `server`. We check both so the function survives a future
    schema move.
    """
    candidates = [server.get("_meta") or {}]
    if entry is not None:
        candidates.insert(0, entry.get("_meta") or {})
    for m in candidates:
        off = m.get("io.modelcontextprotocol.registry/official") or {}
        if off:
            return off
    return {}


def _server_to_repo(server: dict, entry: Optional[dict] = None) -> Optional[dict]:
    """Convert one registry server entry to a repo-shaped dict, or None to drop.
    Filters out:
      - non-active servers (deprecated)
      - duplicate older versions (caller keeps only isLatest=True)
    """
    name = server.get("name")
    description = (server.get("description") or "").strip()
    if not name:
        return None

    meta = _meta_of(server, entry)
    status = meta.get("status", "active")
    if status != "active":
        return None

    updated_at = (meta.get("updatedAt") or meta.get("publishedAt") or "")[:10]
    pushed_at = updated_at  # aliases the "last activity" semantic

    # resolve a GitHub (owner, repo) when possible
    repo = server.get("repository") or {}
    gh = _parse_github_repo(repo.get("url"))
    if gh:
        owner, reponame = gh
        full_name = f"{owner}/{reponame}"
        url = f"https://github.com/{owner}/{reponame}"
        gh_fallback = False
        lang = "—"  # GitHub repo — frontend will overwrite if API returns language
    else:
        # registry-only server — synthesize a pseudo name so the row still surfaces.
        # Replace "/" in registry name with "__" so it doesn't collide with real GH names.
        full_name = "registry/" + name.replace("/", "__")
        url = server.get("websiteUrl") or f"https://registry.modelcontextprotocol.io/v0/servers?cursor={name}"
        gh_fallback = True
        # ponytail: 2026-08 — MCP servers are *services*, not GitHub repos. Tag
        # with "MCP Server" so they don't pollute the "unknown" bucket. The
        # frontend already special-cases '—' for true missing-language GitHub
        # repos (e.g. docs-only awesome-lists).
        lang = "MCP Server"

    # stars: registry has no popularity signal — use position-based score so
    # newer pages rank lower. Caller will pass ranking; here we just stamp 0.
    # The hot_now list is sorted by stars desc; for registry items we promote
    # via "updatedAt" recency by setting score = days-since-epoch proxy.
    try:
        dt = datetime.datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        score = int(dt.timestamp())
    except Exception:
        score = 0

    # topics: surface registry-side signals + transport type
    topics = ["mcp", "mcp-server", "model-context-protocol"]
    for pkg in (server.get("packages") or [])[:2]:
        if pkg.get("registryType"):
            topics.append(f"mcp-{pkg['registryType']}")
    for remote in (server.get("remotes") or [])[:1]:
        if remote.get("type"):
            topics.append(f"mcp-transport-{remote['type']}")

    return {
        "name": full_name,
        "full_name": full_name,
        "url": url,
        "description": description[:500],
        "desc": description[:500],
        "stars": 0,  # registry has no likes; rely on score/updatedAt ordering
        "forks": 0,
        "lang": lang,
        "topics": topics,
        "updated": updated_at,
        "pushed": pushed_at,
        "score": score,
        "best_category": "mcp",
        "is_ai_relevant": True,  # MCP registry is AI-curated by definition
        "source": "mcp_registry",
        "gh_fallback": gh_fallback,  # True = no GitHub mirror; don't try to enrich via gh_fetch_repo
        "mcp_version": server.get("version"),
    }


def fetch_mcp_registry(max_items: int = 60) -> list:
    """Fetch active MCP servers from the official registry.

    - Deduplicates by server name (keeps only the isLatest version).
    - Sorts by updatedAt desc so the freshest servers rise to the top.
    - Returns at most `max_items` entries.

    Falls back to [] on any error — MCP registry being down must NOT block the
    rest of the crawl. We log to stderr so observability stays intact.
    """
    cursor = None
    pages = 0
    latest_per_name: dict[str, tuple[dict, dict]] = {}

    while pages < MAX_PAGES:
        url = REGISTRY_URL + (f"?cursor={cursor}" if cursor else "")
        data = _http_get_json(url, timeout=30)
        if not data:
            print(
                "  [warn] MCP registry: fetch failed (urllib + curl both empty)",
                file=sys.stderr,
            )
            break

        servers = data.get("servers") or []
        if not isinstance(servers, list):
            break

        for entry in servers:
            server = entry.get("server") or {}
            name = server.get("name")
            if not name:
                continue
            meta = _meta_of(server, entry)
            if meta.get("status") != "active":
                continue
            # keep only the latest version per server name — store BOTH the
            # server and the outer entry so _server_to_repo can read meta again
            # during the conversion pass.
            existing = latest_per_name.get(name)
            if existing is None:
                latest_per_name[name] = (server, entry)
            else:
                _, existing_entry = existing
                existing_updated = _meta_of(
                    existing_entry.get("server") or {}, existing_entry
                ).get("updatedAt", "")
                new_updated = meta.get("updatedAt", "")
                if new_updated > existing_updated:
                    latest_per_name[name] = (server, entry)

        cursor = (data.get("metadata") or {}).get("nextCursor")
        pages += 1
        if not cursor:
            break

    out: list[dict] = []
    for server, entry in latest_per_name.values():
        repo = _server_to_repo(server, entry)
        if repo:
            out.append(repo)

    # sort: GitHub-backed first (more discoverable), then by updatedAt desc
    out.sort(
        key=lambda r: (
            not r.get("gh_fallback", True),  # False sorts first
            -(r.get("score") or 0),
        )
    )
    out = out[:max_items]
    print(
        f"  ✓ MCP registry: {len(out)} active servers ({pages} pages, {len(latest_per_name)} unique)",
        file=sys.stderr,
    )
    return out


if __name__ == "__main__":
    # ponytail: manual smoke test — `python3 -m sources.mcp_registry`
    items = fetch_mcp_registry(max_items=10)
    for r in items:
        print(f"  {r['name']:<55} updated={r.get('updated','?')} gh={not r.get('gh_fallback')}")