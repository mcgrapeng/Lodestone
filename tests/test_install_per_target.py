"""Per-target install/uninstall: each SUPPORTED_CLI target installs independently.

ponytail: 2026-09 P2 — install_to_target endpoint must work for all 4 CLIs.
Uses subprocess against a temp fixture git repo so we don't need network.
ponytail: 2026-09 FU-3.1 — uninstall_skill 真正按 CLI 区分,只卸指定 CLI
的 symlink,其它 CLI 保留。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class UninstallPerCLITest(unittest.TestCase):
    """2026-09 FU-3.1:uninstall_skill(name, targets=[cli]) 必须只动指定 CLI,
    其它 CLI 的 symlink + SKILL_ORIGINS.targets + cache 必须保留。"""

    def _seed(self, td: Path, targets=("claude", "codex")) -> dict:
        """Build a fake 'installed to N CLIs' world. Returns {platforms, cache, origins, cache_dir}."""
        platforms = {
            "claude": str(td / ".claude" / "skills"),
            "codex": str(td / ".codex" / "skills"),
            "opencode": str(td / ".config" / "opencode" / "skills"),
            "easycode": str(td / ".easycode" / "skills"),
        }
        cache = td / "cache" / "skills"
        origins_path = td / "origins.json"
        cache_dir = cache / "langflow-ai__langflow"
        cache_dir.mkdir(parents=True, exist_ok=True)
        for p in platforms.values():
            Path(p).mkdir(parents=True, exist_ok=True)
        for cli in targets:
            (Path(platforms[cli]) / "langflow").symlink_to(cache_dir)
        origins_path.write_text(json.dumps({
            "skills": {
                "langflow": {
                    "owner": "langflow-ai",
                    "repo": "langflow",
                    "url": "https://github.com/langflow-ai/langflow",
                    "installed_at": "2026-09-22T10:39:30",
                    "targets": list(targets),
                }
            }
        }))
        return {"platforms": platforms, "cache": cache, "origins": origins_path, "cache_dir": cache_dir}

    def test_per_cli_uninstall_keeps_other_targets(self):
        """Uninstall codex → codex 链接/SKILL_ORIGINS.targets 没了,claude + cache 留着。
        再卸 claude → entry 整个 pop,cache 也清。"""
        from radar_pkg.install import uninstall_skill

        with tempfile.TemporaryDirectory() as td:
            w = self._seed(Path(td), targets=("claude", "codex"))
            with mock.patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", w["platforms"]), \
                 mock.patch("radar_pkg.core.SKILL_ORIGINS", w["origins"]), \
                 mock.patch("radar_pkg.core.SKILLS_CACHE", w["cache"]):
                # step 1: 卸 codex
                r = uninstall_skill("langflow", targets=["codex"])
                self.assertTrue(r["ok"])
                self.assertFalse((Path(w["platforms"]["codex"]) / "langflow").exists())
                self.assertTrue((Path(w["platforms"]["claude"]) / "langflow").is_symlink())
                origins = json.loads(w["origins"].read_text())
                self.assertEqual(origins["skills"]["langflow"]["targets"], ["claude"])
                self.assertTrue(w["cache_dir"].exists(), "per-CLI 卸载后 cache 必须保留")

                # step 2: 卸 claude
                r = uninstall_skill("langflow", targets=["claude"])
                self.assertTrue(r["ok"])
                self.assertFalse((Path(w["platforms"]["claude"]) / "langflow").exists())
                origins = json.loads(w["origins"].read_text())
                self.assertNotIn("langflow", origins["skills"])
                self.assertFalse(w["cache_dir"].exists(), "entry 全清后 cache 必须删")

    def test_uninstall_all_targets_default_unchanged(self):
        """不传 targets → 必须按旧契约一锅端,保留向后兼容。"""
        from radar_pkg.install import uninstall_skill

        with tempfile.TemporaryDirectory() as td:
            w = self._seed(Path(td), targets=("claude", "codex", "opencode"))
            with mock.patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", w["platforms"]), \
                 mock.patch("radar_pkg.core.SKILL_ORIGINS", w["origins"]), \
                 mock.patch("radar_pkg.core.SKILLS_CACHE", w["cache"]):
                r = uninstall_skill("langflow")
                self.assertTrue(r["ok"])
                for cli in ("claude", "codex", "opencode"):
                    self.assertFalse(
                        (Path(w["platforms"][cli]) / "langflow").exists(),
                        f"{cli} 链接未清理",
                    )
                origins = json.loads(w["origins"].read_text())
                self.assertNotIn("langflow", origins["skills"])
                self.assertFalse(w["cache_dir"].exists())

    def test_uninstall_unknown_target_in_list_rejected(self):
        """targets 含不在 SUPPORTED_CLIS 的 CLI → 锁前抛错,不污染 SKILL_ORIGINS。"""
        from radar_pkg.install import uninstall_skill

        with tempfile.TemporaryDirectory() as td:
            w = self._seed(Path(td), targets=("claude", "codex"))
            with mock.patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", w["platforms"]), \
                 mock.patch("radar_pkg.core.SKILL_ORIGINS", w["origins"]), \
                 mock.patch("radar_pkg.core.SKILLS_CACHE", w["cache"]):
                with self.assertRaises(ValueError):
                    uninstall_skill("langflow", targets=["vim"])
                # 原状不动
                self.assertTrue((Path(w["platforms"]["claude"]) / "langflow").is_symlink())
                self.assertTrue((Path(w["platforms"]["codex"]) / "langflow").is_symlink())
                origins = json.loads(w["origins"].read_text())
                self.assertEqual(origins["skills"]["langflow"]["targets"], ["claude", "codex"])


if __name__ == "__main__":
    unittest.main()