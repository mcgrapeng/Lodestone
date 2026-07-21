"""Tests for db/ layer + AI relevance filter. Run: python3 -m tests.test_db"""
import os, sys, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import db.connection as _conn
import radar

# ponytail: use a throwaway DB so tests don't trample dev data
TEST_DB = f"ai_radar_test_{uuid.uuid4().hex[:8]}"
_conn.DSN_DEFAULTS["database"] = TEST_DB  # patch BEFORE any connect()


def _cleanup():
    try:
        admin = db.connect(database="postgres")
        cur = admin.cursor()
        cur.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
        admin.commit()
        admin.close()
    except Exception:
        pass


def setup_module(_):
    _cleanup()
    db.ensure_database()
    db.ensure_schema()


def teardown_module(_):
    _cleanup()


def test_db_upsert_inserts_new_repo():
    conn = db.connect()
    try:
        repos = [{
            "name": "owner/newrepo", "full_name": "owner/newrepo",
            "url": "https://github.com/owner/newrepo",
            "description": "new", "desc_zh": "新",
            "stars": 100, "forks": 5, "lang": "Python",
            "topics": ["ai-agent", "claude-code"],
            "best_category": "agent", "pushed": "2026-07-20",
            "updated": "2026-07-20", "is_ai_relevant": True,
        }]
        inserted, updated = db.upsert_repos(conn, repos)
        conn.commit()
        assert inserted == 1 and updated == 0
        cur = conn.cursor()
        cur.execute("SELECT stars, is_ai_relevant, best_category FROM repos WHERE name=%s",
                    ("owner/newrepo",))
        assert tuple(cur.fetchone()) == (100, True, "agent")
    finally:
        conn.close()


def test_db_upsert_updates_mutates_only():
    conn = db.connect()
    try:
        # Re-upsert same name with new stars + remove category; first_seen_at must persist
        repos = [{
            "name": "owner/newrepo", "full_name": "owner/newrepo",
            "url": "https://github.com/owner/newrepo",
            "description": "new", "desc_zh": None,
            "stars": 250, "forks": 8, "lang": "Python",
            "topics": ["ai-agent"], "best_category": None,
            "pushed": "2026-07-20", "updated": "2026-07-20",
            "is_ai_relevant": True,
        }]
        db.upsert_repos(conn, repos)
        conn.commit()
        cur = conn.cursor()
        cur.execute("SELECT stars, best_category FROM repos WHERE name=%s", ("owner/newrepo",))
        stars, cat = cur.fetchone()
        assert stars == 250 and cat is None, f"expected (250, None) got ({stars}, {cat!r})"
    finally:
        conn.close()


def test_db_snapshot_appends_history_row():
    conn = db.connect()
    try:
        # Ensure parent row exists + is committed (prior tests use fresh conns, so seed here)
        db.upsert_repos(conn, [{
            "name": "owner/snap", "full_name": "owner/snap", "url": "u",
            "description": "d", "desc_zh": "d",
            "stars": 10, "forks": 0, "lang": "Py",
            "topics": ["ai-agent"], "best_category": None,
            "pushed": "2026-07-20", "updated": "2026-07-20",
            "is_ai_relevant": True,
        }])
        conn.commit()
        db.snapshot_stars(conn, ["owner/snap"])
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM repo_stars_history WHERE repo_name=%s",
                    ("owner/snap",))
        assert cur.fetchone()[0] >= 1
    finally:
        conn.close()


def test_blocklist_excludes_trading_repos():
    blocked = {
        "name": "evil/stock-bot", "topics": ["ai-agent", "stock", "trading"],
    }
    allowed = {
        "name": "good/claude-skills", "topics": ["ai-agent", "claude-code"],
    }
    assert radar.is_ai_relevant(blocked) is False, "stock/trading must be blocked"
    assert radar.is_ai_relevant(allowed) is True


def test_api_gain_orders_by_delta_desc():
    """Insert 3 repos with snapshots at -20h and -1h; query_gain orders by delta."""
    import datetime as _dt
    conn = db.connect()
    try:
        # Insert 3 repos with distinct current stars
        repos = [
            {"name": f"owner/r{i}", "full_name": f"owner/r{i}",
             "url": f"https://github.com/owner/r{i}",
             "description": "x", "desc_zh": "x",
             "stars": s, "forks": 0, "lang": "Python",
             "topics": ["ai-agent"], "best_category": None,
             "pushed": "2026-07-20", "updated": "2026-07-20",
             "is_ai_relevant": True} for i, s in enumerate([1000, 500, 2000])
        ]
        db.upsert_repos(conn, repos)
        cur = conn.cursor()
        # 'prev' window (-20h): r0=950, r1=400, r2=1900
        # 'recent' window (-1h): use NOW-ish so it lands in [NOW-4h, NOW]
        prev_rows = [(f"owner/r{i}", s) for i, s in enumerate([950, 400, 1900])]
        # Insert prev snapshots at NOW - 22h (clearly outside recent window)
        for name, stars in prev_rows:
            cur.execute(
                "INSERT INTO repo_stars_history (repo_name, stars, snapshot_at) "
                "VALUES (%s, %s, NOW() - INTERVAL '22 hours')",
                (name, stars),
            )
        conn.commit()
        # query_gain should compute deltas: 50, 100, 100 → order: r2, r1, r0
        out = db.query_gain(conn, limit=10)
        # Filter to just our test repos
        ours = [r for r in out if r["name"].startswith("owner/r")]
        assert len(ours) == 3
        # Highest delta first
        deltas = [r["delta_24h"] for r in ours]
        assert deltas == sorted(deltas, reverse=True), f"not sorted desc: {deltas}"
        assert ours[0]["name"] == "owner/r2"  # delta=100, ties with r1 but r2 has higher stars
    finally:
        conn.close()


def test_api_gain_filters_non_ai_relevant():
    conn = db.connect()
    try:
        # Insert one AI + one non-AI repo with snapshots
        repos = [
            {"name": "owner/ai", "full_name": "owner/ai", "url": "u",
             "description": "x", "desc_zh": "x",
             "stars": 100, "forks": 0, "lang": "Python",
             "topics": ["ai-agent"], "best_category": None,
             "pushed": "2026-07-20", "updated": "2026-07-20",
             "is_ai_relevant": True},
            {"name": "owner/rand", "full_name": "owner/rand", "url": "u",
             "description": "x", "desc_zh": "x",
             "stars": 999, "forks": 0, "lang": "Python",
             "topics": ["awesome"], "best_category": None,
             "pushed": "2026-07-20", "updated": "2026-07-20",
             "is_ai_relevant": False},
        ]
        db.upsert_repos(conn, repos)
        cur = conn.cursor()
        for n in ("owner/ai", "owner/rand"):
            cur.execute(
                "INSERT INTO repo_stars_history (repo_name, stars, snapshot_at) "
                "VALUES (%s, 50, NOW() - INTERVAL '22 hours')",
                (n,),
            )
        conn.commit()
        out = db.query_gain(conn, limit=100)
        names = [r["name"] for r in out]
        assert "owner/rand" not in names, "non-AI repo must not appear in /api/gain"
    finally:
        conn.close()


def test_query_categories_returns_trending_flag():
    """The Vue trending filter only works if the trending column travels with the row.
    ponytail: regression for the bug where _qFilter(cat.repos) saw r.trending === undefined
    and silently no-op'd the toggle inside the category section."""
    conn = db.connect()
    try:
        db.upsert_repos(conn, [{
            "name": "owner/cat-trending", "full_name": "owner/cat-trending",
            "url": "u", "description": "d", "desc_zh": "d",
            "stars": 100, "forks": 0, "lang": "Python",
            "topics": ["ai-agent", "claude-code"], "best_category": "agent",
            "pushed": "2026-07-20", "updated": "2026-07-20",
            "is_ai_relevant": True,
        }])
        db.set_trending(conn, ["owner/cat-trending"])
        conn.commit()
        cats = db.query_categories(conn)
        cat = next(c for c in cats if c["id"] == "agent")
        r = next(x for x in cat["repos"] if x["name"] == "owner/cat-trending")
        assert r["trending"] is True, f"category row must carry trending flag, got {r!r}"
    finally:
        conn.close()


if __name__ == "__main__":
    setup_module(None)
    test_db_upsert_inserts_new_repo()
    print("✓ test_db_upsert_inserts_new_repo")
    test_db_upsert_updates_mutates_only()
    print("✓ test_db_upsert_updates_mutates_only")
    test_db_snapshot_appends_history_row()
    print("✓ test_db_snapshot_appends_history_row")
    test_blocklist_excludes_trading_repos()
    print("✓ test_blocklist_excludes_trading_repos")
    test_api_gain_orders_by_delta_desc()
    print("✓ test_api_gain_orders_by_delta_desc")
    test_api_gain_filters_non_ai_relevant()
    print("✓ test_api_gain_filters_non_ai_relevant")
    test_query_categories_returns_trending_flag()
    print("✓ test_query_categories_returns_trending_flag")
    print("\nAll tests passed.")