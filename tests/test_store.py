"""Tests for lodestone.store.Store (PG-mode; bails cleanly if PG unavailable).
Run: python3 -m tests.test_store"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ponytail: 1.x pattern — bail cleanly if asyncpg/PG unavailable
try:
    import asyncpg
except ImportError:
    print("[test_store] asyncpg unavailable — skipping")
    sys.exit(0)


async def _test():
    test_db = f"lodestone_test_{uuid.uuid4().hex[:8]}"
    import db as lodestone_db
    try:
        lodestone_db.ensure_database(database=test_db)
    except Exception as e:
        print(f"[test_store] cannot create test DB: {e} — skipping")
        return
    lodestone_db.ensure_schema(database=test_db)
    conn = await asyncpg.connect(database=test_db)
    try:
        from lodestone.store import Store
        from lodestone.source import SourceResult
        store = Store(conn)
        await store.ensure_schema()
        r = SourceResult(
            name="owner/repo1", url="https://github.com/owner/repo1",
            description="t", stars=100, forks=5, lang="Python", topics=["ai"],
        )
        is_new = await store.upsert_repo(r, source_name="github")
        assert is_new is True, f"expected True, got {is_new}"
        is_new2 = await store.upsert_repo(r, source_name="github")
        assert is_new2 is False, f"expected False, got {is_new2}"

        repos = await store.list_repos({"limit": 10})
        assert any(x["name"] == "owner/repo1" for x in repos), f"got {[r['name'] for r in repos]}"

        await store.upsert_stars_history("owner/repo1", 105)
        await store.upsert_stars_history("owner/repo1", 110)

        await store.set_plugin_state("github", "token", "ghp_test")
        assert await store.get_plugin_state("github", "token") == "ghp_test"

        nid = await store.insert_notification({
            "kind": "new_repo", "title": "t", "body": "y",
            "repo_name": "owner/repo1", "severity": "info",
        })
        assert nid > 0
        print("✓ test_store_roundtrip")
    finally:
        await conn.close()
        try:
            admin = await asyncpg.connect(database="postgres")
            await admin.execute(f'DROP DATABASE IF EXISTS "{test_db}"')
            await admin.close()
        except Exception:
            pass
    print("\nAll tests passed.")


asyncio.run(_test())
