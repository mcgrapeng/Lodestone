"""Tests for /api/crawl endpoint. Run: python3 -m tests.test_api_crawl"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from lodestone.app import app


def test_crawl_unknown_source_404():
    with TestClient(app) as c:
        r = c.post("/api/crawl?source=does-not-exist")
        assert r.status_code == 404


def test_crawl_all_200():
    with patch("lodestone.app.scheduler.run_now", new=AsyncMock()):
        with TestClient(app) as c:
            r = c.post("/api/crawl")
            assert r.status_code == 200, f"got {r.status_code}: {r.text}"


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
