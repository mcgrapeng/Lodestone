"""Regression test: relaxing AI_TOPIC_HARD must NOT let non-AI repos slip in.

ponytail: 2026-09 P2 — these well-known repos must continue to be excluded
by the AI filter even after the keyword list is widened.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Known NON-AI repos that should NEVER pass `is_ai_relevant`.
KNOWN_NON_AI = [
    ("nvm-sh/nvm", "Node Version Manager", ["node", "version-manager"]),
    ("vuejs/core", "Vue.js framework", ["javascript", "framework"]),
    ("airbnb/javascript", "JS style guide", ["style-guide", "javascript"]),
    ("facebook/react", "React library", ["javascript", "ui"]),
    ("microsoft/vscode", "VS Code editor", ["editor", "typescript"]),
    ("oven-sh/bun", "JS runtime", ["javascript", "runtime"]),
]


class AiFilterTest(unittest.TestCase):
    def test_known_non_ai_excluded(self):
        """None of these well-known non-AI repos should pass the AI filter."""
        from radar_pkg.core import is_ai_relevant
        for name, desc, topics in KNOWN_NON_AI:
            repo = {
                "name": name,
                "description": desc,
                "topics": topics,
            }
            result = is_ai_relevant(repo)
            self.assertFalse(
                result, f"{name} should NOT pass AI filter (relaxed AI_TOPIC_HARD regression)"
            )


if __name__ == "__main__":
    unittest.main()
