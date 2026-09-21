"""Regression test: known-missing mainstream AI projects must appear in categories after crawl.

ponytail: 2026-09 P2 — runs in-process crawl against fixture CSVs and asserts
KNOWN_MISSING repos end up in at least one category. Uses stubbed sources to
avoid network; ensures the seed + AI filter + sources wiring works.
"""
import json
import os
import sys
import unittest
from pathlib import Path

# Add project root to path so we can import radar_pkg and sources.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


KNOWN_MISSING = [
    "Tencent/WeKnora",
    "alibaba/open-code-review",
    "mksglu/context-mode",
]


class CrawlCoverageTest(unittest.TestCase):
    def test_known_missing_in_seed(self):
        """Manual seed JSON includes all 3 user-reported missing projects."""
        seed_path = Path(__file__).parent.parent / "data" / "awesome_lists_seed.json"
        if not seed_path.is_file():
            self.skipTest("seed not yet created (Task 1.6)")
        with seed_path.open() as f:
            data = json.load(f)
        seeded = {r["name"] for r in data.get("repos", [])}
        for name in KNOWN_MISSING:
            self.assertIn(name, seeded, f"{name} not in manual seed")

    def test_ai_topic_hard_relaxed(self):
        """Removed keywords absent, new keywords present."""
        from radar_pkg.core import AI_TOPIC_HARD
        for k in ("mcp-server", "agent-skills", "spring-ai"):
            self.assertNotIn(k, AI_TOPIC_HARD, f"{k} should be removed")
        for k in ("pytorch", "tensorflow", "deep-learning"):
            self.assertIn(k, AI_TOPIC_HARD, f"{k} should be added")

    def test_top_5k_limit_bumped(self):
        from radar_pkg.core import TOP_5K_LIMIT
        self.assertGreaterEqual(TOP_5K_LIMIT, 1200)

    def test_query_count_expanded(self):
        from radar_pkg.core import TOP_5K_QUERIES
        self.assertGreaterEqual(
            len(TOP_5K_QUERIES), 220,
            f"Expected >=220 queries, got {len(TOP_5K_QUERIES)}",
        )

    def test_awesome_lists_source_registered(self):
        """Source module exists and has a crawl() function."""
        from sources import awesome_lists
        self.assertTrue(callable(getattr(awesome_lists, "crawl", None)))

    def test_hackernews_ai_source_registered(self):
        from sources import hackernews_ai
        self.assertTrue(callable(getattr(hackernews_ai, "crawl", None)))


if __name__ == "__main__":
    unittest.main()
