"""Tests for /api/notifications endpoint. PG-mode; bails cleanly if PG unavailable.
Run: python3 -m tests.test_api_notifications"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import asyncpg
except ImportError:
    print("[test_api_notifications] asyncpg unavailable — skipping")
    sys.exit(0)

import os


def test_notifications_503_when_no_db():
    """When DB unavailable, /api/notifications returns 503 (matches other endpoints)."""
    from fastapi.testclient import TestClient
    # Force no DATABASE_URL so lifespan fails to connect
    old = os.environ.pop("DATABASE_URL", None)
    os.environ["DATABASE_URL"] = "postgresql://nonexistent_user:nonexistent_pass@127.0.0.1:1/nonexistent"
    try:
        from lodestone.app import app
        with TestClient(app) as c:
            r = c.get("/api/notifications")
            assert r.status_code == 503, f"expected 503, got {r.status_code}"
    finally:
        if old:
            os.environ["DATABASE_URL"] = old
        else:
            os.environ.pop("DATABASE_URL", None)


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
