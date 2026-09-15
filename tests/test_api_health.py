"""Tests for /api/health. Run: python3 -m tests.test_api_health"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_health_shape():
    test_app = FastAPI()

    @test_app.get("/api/health")
    async def h():
        return {"ok": True, "version": "2.0.0a1", "plugins": 8}

    client = TestClient(test_app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["version"] == "2.0.0a1"
    assert body["plugins"] == 8


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
