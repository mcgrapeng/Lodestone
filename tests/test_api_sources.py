"""Tests for /api/sources endpoint. Run: python3 -m tests.test_api_sources"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from lodestone.app import app


def test_list_sources_returns_8():
    with TestClient(app) as c:
        r = c.get("/api/sources")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 8, f"expected 8 plugins, got {len(body)}: {[p['name'] for p in body]}"
        names = {p["name"] for p in body}
        assert {"github", "huggingface", "mcp_registry", "arxiv",
                "recency", "stars", "in_app", "webhook"} == names


def test_get_source_unknown_404():
    with TestClient(app) as c:
        r = c.get("/api/sources/does-not-exist")
        assert r.status_code == 404


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
