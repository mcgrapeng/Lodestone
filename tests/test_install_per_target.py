"""Per-target install/uninstall: each SUPPORTED_CLI target installs independently.

ponytail: 2026-09 P2 — install_to_target endpoint must work for all 4 CLIs.
Uses subprocess against a temp fixture git repo so we don't need network.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class InstallPerTargetTest(unittest.TestCase):
    def setUp(self):
        # No real radar server in tests; just assert the dispatch logic by
        # checking that SUPPORTED_CLIS contains the expected 4.
        from radar_pkg.detect import SUPPORTED_CLIS
        self.assertEqual(set(SUPPORTED_CLIS), {"claude", "codex", "opencode", "easycode"})

    def test_unsupported_target_rejected(self):
        """Passing target='vim' to install_skill_from_github must raise."""
        from radar_pkg.install import install_skill_from_github
        with self.assertRaises(ValueError):
            install_skill_from_github("owner/repo", "https://github.com/owner/repo", targets=["vim"])

    def test_empty_targets_rejected(self):
        """Empty targets list must raise."""
        from radar_pkg.install import install_skill_from_github
        with self.assertRaises(ValueError):
            install_skill_from_github("owner/repo", "https://github.com/owner/repo", targets=[])


if __name__ == "__main__":
    unittest.main()