"""Tests for db/ layer. Run: python3 -m tests.test_db
Skips gracefully when pg8000/Postgres unavailable (JSON-only mode)."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import db  # noqa: E402

if not db._DB_OK:
    print("[test_db] pg8000 unavailable — skipping (JSON-only mode)")
    sys.exit(0)

import db.connection as _conn  # noqa: E402

# ponytail: use a throwaway DB so tests don't trample dev data
TEST_DB = f"ai_radar_test_{uuid.uuid4().hex[:8]}"
# patch the shared defaults dict BEFORE any connect(); PG* env still override in _dsn,
# so also force database through the same override the caller would use.
_conn.DSN_DEFAULTS["database"] = TEST_DB


def _cleanup():
    try:
        admin = db.connect(database="postgres")
        cur = admin.cursor()
        cur.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
        admin.commit()
        admin.close()
    except Exception:
        pass


def _q(**kw):
    """connect() with the test database forced, immune to PGDATABASE env."""
    return db.connect(database=TEST_DB, **kw)


def setup_module(_):
    _cleanup()
    db.ensure_database(database=TEST_DB)
    db.ensure_schema(database=TEST_DB)


def teardown_module(_):
    _cleanup()


def test_db_upsert_real_counts():
    """First upsert inserts; second upserts (updates) — counts must be real, not len(rows)."""
    conn = _q()
    try:
        repo = {
            "name": "owner/newrepo",
            "full_name": "owner/newrepo",
            "url": "https://github.com/owner/newrepo",
            "description": "new",
            "desc_zh": "新",
            "stars": 100,
            "forks": 5,
            "lang": "Python",
            "topics": ["ai-agent", "claude-code"],
            "best_category": "agent",
            "pushed": "2026-07-20",
            "updated": "2026-07-20",
            "is_ai_relevant": True,
        }
        inserted, updated = db.upsert_repos(conn, [repo])
        conn.commit()
        assert (inserted, updated) == (1, 0), (
            f"expected (1,0) got ({inserted},{updated})"
        )
        repo["stars"] = 250
        inserted, updated = db.upsert_repos(conn, [repo])
        conn.commit()
        assert (inserted, updated) == (0, 1), (
            f"expected (0,1) got ({inserted},{updated})"
        )
        cur = conn.cursor()
        cur.execute("SELECT stars FROM repos WHERE name=%s", ("owner/newrepo",))
        assert cur.fetchone()[0] == 250
    finally:
        conn.close()


def test_db_upsert_preserves_first_seen_and_desc():
    conn = _q()
    try:
        db.upsert_repos(
            conn,
            [
                {
                    "name": "owner/keep",
                    "full_name": "owner/keep",
                    "url": "u",
                    "description": "old desc",
                    "desc_zh": "旧",
                    "stars": 10,
                    "forks": 0,
                    "lang": "Py",
                    "topics": ["ai-agent"],
                    "best_category": None,
                    "pushed": "2026-07-20",
                    "updated": "2026-07-20",
                    "is_ai_relevant": True,
                }
            ],
        )
        conn.commit()
        # re-upsert with EMPTY description — COALESCE must keep the old one
        db.upsert_repos(
            conn,
            [
                {
                    "name": "owner/keep",
                    "full_name": "owner/keep",
                    "url": "u",
                    "description": None,
                    "desc_zh": None,
                    "stars": 20,
                    "forks": 0,
                    "lang": "Py",
                    "topics": ["ai-agent"],
                    "best_category": None,
                    "pushed": "2026-07-20",
                    "updated": "2026-07-20",
                    "is_ai_relevant": True,
                }
            ],
        )
        conn.commit()
        cur = conn.cursor()
        cur.execute(
            "SELECT description, stars FROM repos WHERE name=%s", ("owner/keep",)
        )
        desc, stars = cur.fetchone()
        assert desc == "old desc" and stars == 20
    finally:
        conn.close()


def test_db_snapshot_appends_history_row():
    conn = _q()
    try:
        db.upsert_repos(
            conn,
            [
                {
                    "name": "owner/snap",
                    "full_name": "owner/snap",
                    "url": "u",
                    "description": "d",
                    "desc_zh": "d",
                    "stars": 10,
                    "forks": 0,
                    "lang": "Py",
                    "topics": ["ai-agent"],
                    "best_category": None,
                    "pushed": "2026-07-20",
                    "updated": "2026-07-20",
                    "is_ai_relevant": True,
                }
            ],
        )
        conn.commit()
        db.snapshot_stars(conn, ["owner/snap"])
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM repo_stars_history WHERE repo_name=%s",
            ("owner/snap",),
        )
        assert cur.fetchone()[0] >= 1
    finally:
        conn.close()


def test_api_gain_orders_by_delta_desc():
    """Insert 3 repos with snapshots at -22h; query_gain orders by delta desc."""
    conn = _q()
    try:
        repos = [
            {
                "name": f"owner/r{i}",
                "full_name": f"owner/r{i}",
                "url": f"https://github.com/owner/r{i}",
                "description": "x",
                "desc_zh": "x",
                "stars": s,
                "forks": 0,
                "lang": "Python",
                "topics": ["ai-agent"],
                "best_category": None,
                "pushed": "2026-07-20",
                "updated": "2026-07-20",
                "is_ai_relevant": True,
            }
            for i, s in enumerate([1000, 500, 2000])
        ]
        db.upsert_repos(conn, repos)
        cur = conn.cursor()
        # prev window (-20h cutoff): snapshots at -22h → r0=950, r1=400, r2=1900
        for i, s in enumerate([950, 400, 1900]):
            cur.execute(
                "INSERT INTO repo_stars_history (repo_name, stars, snapshot_at) "
                "VALUES (%s, %s, NOW() - INTERVAL '22 hours')",
                (f"owner/r{i}", s),
            )
        conn.commit()
        # recent window: current stars snapshotted at NOW() → deltas 50, 100, 100
        db.snapshot_stars(conn, [f"owner/r{i}" for i in range(3)])
        conn.commit()
        out = db.query_gain(
            conn, prev_ago="20 hours", recent_ago="4 hours", min_delta=0, size=10
        )
        ours = [r for r in out["gainers"] if r["name"].startswith("owner/r")]
        assert len(ours) == 3
        deltas = [r["delta_24h"] for r in ours]
        assert deltas == sorted(deltas, reverse=True), f"not sorted desc: {deltas}"
        assert (
            ours[0]["name"] == "owner/r2"
        )  # delta=100, ties with r1 but r2 has higher stars
    finally:
        conn.close()


def test_api_gain_filters_non_ai_relevant():
    conn = _q()
    try:
        repos = [
            {
                "name": "owner/ai",
                "full_name": "owner/ai",
                "url": "u",
                "description": "x",
                "desc_zh": "x",
                "stars": 100,
                "forks": 0,
                "lang": "Python",
                "topics": ["ai-agent"],
                "best_category": None,
                "pushed": "2026-07-20",
                "updated": "2026-07-20",
                "is_ai_relevant": True,
            },
            {
                "name": "owner/rand",
                "full_name": "owner/rand",
                "url": "u",
                "description": "x",
                "desc_zh": "x",
                "stars": 999,
                "forks": 0,
                "lang": "Python",
                "topics": ["awesome"],
                "best_category": None,
                "pushed": "2026-07-20",
                "updated": "2026-07-20",
                "is_ai_relevant": False,
            },
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
        db.snapshot_stars(conn, ["owner/ai", "owner/rand"])  # recent window rows
        conn.commit()
        out = db.query_gain(
            conn, prev_ago="20 hours", recent_ago="4 hours", min_delta=0, size=100
        )
        names = [r["name"] for r in out["gainers"]]
        assert "owner/rand" not in names, "non-AI repo must not appear in /api/gain"
    finally:
        conn.close()


def test_query_categories_returns_trending_flag():
    """The Vue trending filter only works if the trending column travels with the row."""
    conn = _q()
    try:
        db.upsert_repos(
            conn,
            [
                {
                    "name": "owner/cat-trending",
                    "full_name": "owner/cat-trending",
                    "url": "u",
                    "description": "d",
                    "desc_zh": "d",
                    "stars": 100,
                    "forks": 0,
                    "lang": "Python",
                    "topics": ["ai-agent", "claude-code"],
                    "best_category": "agent",
                    "pushed": "2026-07-20",
                    "updated": "2026-07-20",
                    "is_ai_relevant": True,
                }
            ],
        )
        db.set_trending(conn, ["owner/cat-trending"])
        conn.commit()
        cats = db.query_categories(conn)
        cat = next(c for c in cats if c["id"] == "agent")
        r = next(x for x in cat["repos"] if x["name"] == "owner/cat-trending")
        assert r["trending"] is True, (
            f"category row must carry trending flag, got {r!r}"
        )
    finally:
        conn.close()


def test_crawl_log_records_queries_failed():
    conn = _q()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO crawl_log DEFAULT VALUES RETURNING id")
        cid = cur.fetchone()[0]
        cur.execute(
            "UPDATE crawl_log SET finished_at=NOW(), queries_failed=%s WHERE id=%s",
            (3, cid),
        )
        conn.commit()
        cur.execute("SELECT queries_failed FROM crawl_log WHERE id=%s", (cid,))
        assert cur.fetchone()[0] == 3
    finally:
        conn.close()


if __name__ == "__main__":
    setup_module(None)
    for name, fn in sorted(
        {
            k: v
            for k, v in list(globals().items())
            if k.startswith("test_") and callable(v)
        }.items()
    ):
        fn()
        print(f"✓ {name}")
    teardown_module(None)
    print("\nAll tests passed.")
