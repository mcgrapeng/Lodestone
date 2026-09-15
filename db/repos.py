"""Repo-level CRUD + queries. All callers pass a pg8000 connection."""

import json
from typing import Iterable

# ponytail: int IDs serve double duty as default sort column for /api/top
_TOP_SORT_SQL = {
    "stars": "stars DESC",
    "recent": "pushed_at DESC NULLS LAST, stars DESC",
    "name": "name ASC",
}


def _cols(cur):
    """pg8000 returns description tuples — extract column names from index 0."""
    return [d[0] for d in cur.description] if cur.description else []


def _dicts(cur):
    """Materialize rows as dicts; coerce date/datetime to ISO strings so json.dumps works."""
    out = []
    cols = _cols(cur)
    if not cols:
        return out
    for row in cur.fetchall():
        d = {}
        for k, v in zip(cols, row):
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            d[k] = v
        out.append(d)
    return out


def upsert_repos(conn, repos: Iterable[dict]):
    """Bulk upsert into repos. ON CONFLICT (name) updates mutable fields only.
    Note: 'trending' is NOT set here — caller manages it via set_trending() after crawl.
    Note: 'stars_today' is updated ONLY when the caller supplies it (trending scrape) — non-trending repos
    keep their previous value, so we don't accidentally null it out on a normal category crawl.
    Returns (inserted, updated) with REAL counts — we check which names already exist first
    (ponytail: pg8000 executemany rowcount can't distinguish insert vs update)."""
    repos = list(repos)
    if not repos:
        return 0, 0
    cur = conn.cursor()
    names = [r["name"] for r in repos]
    cur.execute("SELECT name FROM repos WHERE name = ANY(%s)", (names,))
    existing = {row[0] for row in cur.fetchall()}
    rows = [
        (
            r["name"],
            r.get("full_name") or r["name"],
            r["url"],
            r.get("description") or r.get("desc"),
            r.get("desc_zh"),
            int(r.get("stars") or 0),
            int(r.get("forks") or 0),
            r.get("lang") or None,
            list(r.get("topics") or []),
            r.get("best_category") or None,
            r.get("pushed") or None,
            r.get("updated") or None,
            bool(r.get("is_ai_relevant")),
            r.get("stars_today"),  # may be None — only trending scrape fills this
            bool(r.get("is_skill")),  # 2026-09 — SKILL.md probe
            json.dumps(r.get("summary_sections") or {})  # {intro, can_do, benefit}
            if r.get("summary_sections")
            else None,
            json.dumps(r.get("analysis_5d") or {})  # 2026-09 — LLM 5 维度决策分析
            if r.get("analysis_5d")
            else None,
        )
        for r in repos
    ]
    cur.executemany(
        """
        INSERT INTO repos (name, full_name, url, description, desc_zh,
                           stars, forks, lang, topics, best_category,
                           pushed_at, updated_at, is_ai_relevant, stars_today,
                           is_skill, summary_sections_json, analysis_5d_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (name) DO UPDATE SET
          stars         = EXCLUDED.stars,
          forks         = EXCLUDED.forks,
          lang          = EXCLUDED.lang,
          topics        = EXCLUDED.topics,
          -- 2026-09 P3: COALESCE 防退化 — 多源(MCP/arXiv/GitHub)同名行互相覆盖时,
          -- 空 pushed/updated 不再抹掉已有真值(此前 NULL 直接覆盖)。
          pushed_at     = COALESCE(EXCLUDED.pushed_at, repos.pushed_at),
          updated_at    = COALESCE(EXCLUDED.updated_at, repos.updated_at),
          description   = COALESCE(EXCLUDED.description, repos.description),
          desc_zh       = COALESCE(EXCLUDED.desc_zh, repos.desc_zh),
          is_ai_relevant = EXCLUDED.is_ai_relevant,
          best_category = EXCLUDED.best_category,
          stars_today   = COALESCE(EXCLUDED.stars_today, repos.stars_today),
          is_skill      = EXCLUDED.is_skill,
          summary_sections_json = COALESCE(EXCLUDED.summary_sections_json, repos.summary_sections_json),
          analysis_5d_json      = COALESCE(EXCLUDED.analysis_5d_json, repos.analysis_5d_json),
          last_seen_at  = NOW()
    """,
        rows,
    )
    inserted = sum(1 for n in names if n not in existing)
    return inserted, len(rows) - inserted


def set_trending(conn, names: Iterable[str]):
    """Mark repos as trending today. Resets stale flags first so only currently-trending repos stay flagged."""
    cur = conn.cursor()
    cur.execute("UPDATE repos SET trending = FALSE")
    cur.execute("UPDATE repos SET trending = TRUE WHERE name = ANY(%s)", (list(names),))


def replace_categories(conn, repo_cats: list[tuple[str, str]]):
    """repo_cats: list of (repo_name, category_id). Wipes existing rows for affected repos first."""
    if not repo_cats:
        return 0
    cur = conn.cursor()
    names = list({n for n, _ in repo_cats})
    cur.execute("DELETE FROM repo_categories WHERE repo_name = ANY(%s)", (names,))
    cur.executemany(
        "INSERT INTO repo_categories (repo_name, category_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        repo_cats,
    )
    return len(repo_cats)


def snapshot_stars(conn, repo_names: list[str]):
    """Append a (repo_name, stars, today) row for every repo in repo_names.
    2026-09 P3: snapshot_at 截断到当天 — (repo, snapshot_at) 主键 + ON CONFLICT
    使同日多次 crawl 只记一行(旧行已由 schema.sql 迁移归一)。"""
    if not repo_names:
        return 0
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO repo_stars_history (repo_name, snapshot_at, stars)
        SELECT name, date_trunc('day', NOW()), stars FROM repos WHERE name = ANY(%s)
        ON CONFLICT DO NOTHING
    """,
        (repo_names,),
    )
    return cur.rowcount or 0


def query_top_5k(conn, page: int = 1, size: int = 12, sort: str = "stars"):
    """Paginate the top tier: AI-relevant repos with >= 1000 stars regardless of category.
    ponytail: previously gated by `best_category IS NULL` which hid 100k-star projects like
    openai/codex. Lowered 5000 → 1000 to surface lidge-jun/opencodex (1295⭐) and similar.
    Manual-seeded low-star repos stay in DB (maintained by MANUAL_SEED_REPOS in radar.py)
    but do NOT bypass the star gate here — putting 0⭐ repos in a "5k+ 顶级" view is
    confusing for users."""
    sort_sql = _TOP_SORT_SQL.get(sort, _TOP_SORT_SQL["stars"])
    offset = max(0, (page - 1) * size)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM repos WHERE is_ai_relevant AND stars >= 1000")
    total = cur.fetchone()[0]
    cur.execute(
        f"""
        SELECT name, url, description, desc_zh, stars, forks, lang, topics,
               pushed_at, updated_at, trending, first_seen_at, stars_today,
               is_skill,
               summary_sections_json AS summary_sections,
               analysis_5d_json AS analysis_5d
        FROM repos
        WHERE is_ai_relevant AND stars >= 1000
        ORDER BY {sort_sql}
        LIMIT %s OFFSET %s
    """,
        (size, offset),
    )
    repos = [d | {"local_installed": False} for d in _dicts(cur)]
    return {
        "repos": repos,
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
        "sort": sort,
    }


def query_all_repos_for_summarize(conn):
    """summarize_repos() 用:全量取 AI 相关 repos(stars+topic+raw_md 字段都带上)。

    不分页 — summarize 是后台批量任务,一次跑完所有候选。LLM analyze_one
    自己按 _min_stars() 阈值过滤(避免给 0⭐ 项目浪费 token)。
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name, url, description, desc_zh, stars, forks, lang, topics,
               pushed_at, updated_at, trending, first_seen_at, stars_today,
               is_skill,
               summary_sections_json AS summary_sections,
               analysis_5d_json AS analysis_5d
        FROM repos
        WHERE is_ai_relevant
        ORDER BY stars DESC
    """
    )
    return [d | {"local_installed": False} for d in _dicts(cur)]


def query_hot_now(conn, limit: int = 40):
    """Top AI repos by stars overall."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name, url, description, desc_zh, stars, forks, lang, topics,
               pushed_at, updated_at, trending, first_seen_at, stars_today,
               is_skill,
               summary_sections_json AS summary_sections,
               analysis_5d_json AS analysis_5d
        FROM repos WHERE is_ai_relevant
        ORDER BY stars DESC LIMIT %s
    """,
        (limit,),
    )
    return [d | {"local_installed": False} for d in _dicts(cur)]


def query_categories(conn):
    """Group by best_category. Return [{id, name, desc, count, repos: [...]}]."""
    cur = conn.cursor()
    cat_meta = {}
    try:
        from radar_pkg.core import CATEGORIES  # canonical source (was: late import from radar)

        cat_meta = {c["id"]: (c["name"], c["desc"]) for c in CATEGORIES}
    except Exception:
        pass
    cur.execute("""
        SELECT best_category, name, url, description, desc_zh, stars, forks,
               lang, topics, pushed_at, updated_at, trending, first_seen_at, stars_today,
               is_skill,
               summary_sections_json AS summary_sections,
               analysis_5d_json AS analysis_5d
        FROM repos
        WHERE is_ai_relevant AND best_category IS NOT NULL
        ORDER BY best_category, stars DESC
    """)
    grouped: dict[str, list] = {}
    for d in _dicts(cur):
        cid = d.pop("best_category")
        d["local_installed"] = False
        grouped.setdefault(cid, []).append(d)
    return [
        {
            "id": cid,
            "name": cat_meta.get(cid, cid)[0],
            "desc": cat_meta.get(cid, "")[1],
            "count": len(rs),
            "repos": rs,
        }
        for cid, rs in grouped.items()
    ]


def query_gain(
    conn,
    prev_ago: str,
    recent_ago: str,
    min_delta: int = 100,
    page: int = 1,
    size: int = 24,
):
    """24h star gainers. Primary source: `repos.stars_today` (populated from github.com/trending
    "X stars today" — the literal 24h delta). Falls back to repo_stars_history delta when ≥20h of
    snapshots exist. Both sources agree on the meaning, so we union them and dedupe on repo name
    (snapshot delta wins when present, since it covers repos not currently on the trending page).
    Returns {gainers, total, page, size, pages, min_delta}."""
    # ponytail: validate intervals client-side to avoid SQL injection via the %s interpolation
    import re

    if not re.match(
        r"^\d+ (hour|day|week|minute)s?(\s\d+ (hour|day|week|minute)s?)*$", prev_ago
    ):
        raise ValueError(f"invalid prev_ago: {prev_ago!r}")
    if not re.match(
        r"^\d+ (hour|day|week|minute)s?(\s\d+ (hour|day|week|minute)s?)*$", recent_ago
    ):
        raise ValueError(f"invalid recent_ago: {recent_ago!r}")

    offset = max(0, (page - 1) * size)
    cur = conn.cursor()
    cur.execute(
        f"""
        WITH trending_gain AS (
            SELECT name, stars_today AS delta_24h, FALSE AS cold_start
            FROM repos
            WHERE is_ai_relevant AND stars_today IS NOT NULL AND stars_today >= %s
        ),
        snapshot_gain AS (
            WITH prev AS (
                SELECT DISTINCT ON (repo_name) repo_name, stars AS s_prev
                FROM repo_stars_history
                WHERE snapshot_at <= NOW() - INTERVAL '{prev_ago}'
                ORDER BY repo_name, snapshot_at DESC
            ),
            recent AS (
                SELECT DISTINCT ON (repo_name) repo_name, stars AS s_now
                FROM repo_stars_history
                WHERE snapshot_at >= NOW() - INTERVAL '{recent_ago}'
                ORDER BY repo_name, snapshot_at DESC
            )
            SELECT r.name, (recent.s_now - prev.s_prev) AS delta_24h, FALSE AS cold_start
            FROM repos r
            JOIN prev   ON prev.repo_name   = r.name
            JOIN recent ON recent.repo_name = r.name
            WHERE r.is_ai_relevant
              AND (recent.s_now - prev.s_prev) >= %s
        ),
        combined AS (
            SELECT * FROM trending_gain
            UNION
            SELECT * FROM snapshot_gain WHERE name NOT IN (SELECT name FROM trending_gain)
        ),
        ranked AS (
            SELECT c.name, r.url, r.description, r.desc_zh, r.stars, r.lang,
                   r.topics, r.pushed_at, c.delta_24h, c.cold_start,
                   r.summary_zh,
                   r.summary_sections_json AS summary_sections,
                   r.analysis_5d_json AS analysis_5d,
                   r.is_skill, r.stars_today
            FROM combined c
            JOIN repos r ON r.name = c.name
        )
        SELECT *, (SELECT COUNT(*) FROM ranked) AS total
        FROM ranked
        ORDER BY delta_24h DESC, stars DESC
        LIMIT %s OFFSET %s
    """,
        (min_delta, min_delta, size, offset),
    )
    rows = _dicts(cur)
    total = rows[0]["total"] if rows else 0
    for d in rows:
        d.pop("total", None)
        d["local_installed"] = False
    return {
        "gainers": rows,
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
        "min_delta": min_delta,
    }
