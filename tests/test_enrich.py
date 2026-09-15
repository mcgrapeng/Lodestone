"""Tests for enrichment state + 2 endpoints. Run: python3 -m tests.test_enrich"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone import enrich
from fastapi.testclient import TestClient
from lodestone.app import app


def test_enrich_state_lifecycle():
    # Clean slate
    enrich.clear()
    assert enrich.is_enriched() is False
    assert enrich.enriched_at() is None

    # Mark enriched
    ts = enrich.mark_enriched()
    assert ts
    assert enrich.is_enriched() is True
    assert enrich.enriched_at() == ts

    # Clear
    enrich.clear()
    assert enrich.is_enriched() is False
    assert enrich.enriched_at() is None


def test_enrich_endpoints_via_testclient():
    enrich.clear()
    with TestClient(app) as c:
        r1 = c.get("/api/enrich/status")
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["enriched"] is False
        assert body1["at"] is None

        r2 = c.post("/api/enrich/mark")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["ok"] is True
        assert body2["at"]
        # The marker file should exist now
        assert enrich.is_enriched() is True

        r3 = c.get("/api/enrich/status")
        assert r3.json()["enriched"] is True
        assert r3.json()["at"] == body2["at"]

        r4 = c.post("/api/enrich/reset")
        assert r4.status_code == 200
        assert enrich.is_enriched() is False
    # cleanup
    enrich.clear()


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
