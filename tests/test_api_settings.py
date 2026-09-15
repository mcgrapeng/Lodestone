"""Tests for /api/settings (1.x-compatible). Run: python3 -m tests.test_api_settings"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from lodestone.app import app


def test_settings_roundtrip():
    with TestClient(app) as c:
        r1 = c.post("/api/settings",
                     json={"provider": "openai",
                            "openai": {"api_key": "sk-test", "model": "gpt-4o-mini"}})
        assert r1.status_code == 200, f"got {r1.status_code}: {r1.text}"
        r2 = c.get("/api/settings")
        assert r2.status_code == 200
        body = r2.json()
        assert body["provider"] == "openai"
        assert body["openai"]["model"] == "gpt-4o-mini"
    # cleanup
    p = Path("data/settings.json")
    if p.exists():
        p.unlink()


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
