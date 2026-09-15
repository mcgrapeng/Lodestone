"""Tests for the built-in scorers. Run: python3 -m tests.test_scorers"""
import asyncio
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.plugins.scorer_recency import RecencyScorer
from lodestone.plugins.scorer_stars import StarsScorer


def test_recency_fresh_repo_high_score():
    sc = RecencyScorer()
    fresh = {"last_seen_at": datetime.now(timezone.utc).isoformat()}
    s = asyncio.run(sc.score(fresh, {}))
    assert s.value > 0.9, f"expected > 0.9, got {s.value}"


def test_recency_old_repo_zero():
    sc = RecencyScorer()
    old = {"last_seen_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()}
    s = asyncio.run(sc.score(old, {}))
    assert s.value == 0.0, f"expected 0.0, got {s.value}"


def test_stars_saturates():
    sc = StarsScorer()
    s_low = asyncio.run(sc.score({"stars": 10}, {}))
    s_mid = asyncio.run(sc.score({"stars": 100}, {}))
    s_high = asyncio.run(sc.score({"stars": 50000}, {}))
    assert s_low.value < s_mid.value < s_high.value <= 1.0
    assert s_mid.value == 0.5


def test_stars_zero():
    sc = StarsScorer()
    s = asyncio.run(sc.score({"stars": 0}, {}))
    assert s.value == 0.0


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
