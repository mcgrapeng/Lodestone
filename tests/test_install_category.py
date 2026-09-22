"""Tests for /api/install_category and /api/uninstall_category endpoints.

ponytail: 2026-09 FU-marquee — 这些 endpoint 把"一键安装/卸载整个分类"包到
server 侧,跑后台 daemon thread 处理 30s clone × N,前端轮询
/api/install/status 看进度。这里只断 endpoint 契约(response shape +
immediate validation)——thread 内部逻辑由 test_install_per_target.py 覆盖。
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from radar_pkg import core  # noqa: E402

DATA = core.DATA
BASE = "http://127.0.0.1:8765"


def _curl(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    args = [
        "curl", "-sS", "-X", method, BASE + path,
        "-w", "\n__HTTP__%{http_code}",
        "-H", "Content-Type: application/json",
    ]
    if payload is not None:
        args.extend(["-d", json.dumps(payload)])
    r = subprocess.run(args, capture_output=True, text=True, timeout=10)
    body, _, status_line = r.stdout.rpartition("__HTTP__")
    body = body.strip()
    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError:
        parsed = {"_raw": body}
    return int(status_line), parsed


class InstallCategoryEndpointTest(unittest.TestCase):
    """Contract tests for /api/install_category + /api/uninstall_category."""

    TEST_CAT = "pytest-fixture-cat"

    def setUp(self):
        self._latest = DATA / "latest.json"
        self._saved = self._latest.read_bytes() if self._latest.exists() else None

    def tearDown(self):
        # 恢复被测试改写的 latest.json。
        if self._saved is not None:
            self._latest.write_bytes(self._saved)
        elif self._latest.exists():
            self._latest.unlink()

    def _seed_latest(self, repos: list[dict]) -> None:
        fixture = {"categories": [{"id": self.TEST_CAT, "repos": repos}]}
        self._latest.write_text(json.dumps(fixture))

    def test_install_category_rejects_invalid_target(self):
        """target 不在 SUPPORTED_CLIS → 400,body 含 CLI 列表。"""
        # ponytail: 不需要 latest.json 也能测——纯 validation 就被前端拒绝。
        status, body = _curl("POST", "/api/install_category",
                             {"category_id": "agent", "target": "vim"})
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        self.assertIn("codex", body["error"])

    def test_install_category_filters_non_skills(self):
        """is_skill=false 的 repo 必须被剔除,total 只数到真正的 skill。"""
        self._seed_latest([
            {"name": "owner/yes-skill", "url": "https://github.com/owner/yes-skill", "is_skill": True},
            {"name": "owner/not-skill", "url": "https://github.com/owner/not-skill", "is_skill": False},
        ])
        # except_ 把 is_skill=true 那个也排掉,让后台 thread 啥也不装,免得 30s/个
        # 真实 clone 拖慢测试。我们只关心 immediate response 的 total 计数。
        status, body = _curl("POST", "/api/install_category",
                             {"category_id": self.TEST_CAT, "target": "codex",
                              "except": ["owner/yes-skill"]})
        self.assertEqual(status, 200)
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("target"), "codex")
        self.assertEqual(body.get("total"), 0,
                         "is_skill=false 应被剔除,except_ 全排除后 total=0")

    def test_uninstall_category_rejects_unknown_category(self):
        """latest.json 存在但 cat_id 不在 → 400 + 报'unknown category'。"""
        self._seed_latest([
            {"name": "owner/skill", "url": "https://github.com/owner/skill", "is_skill": True},
        ])
        status, body = _curl("POST", "/api/uninstall_category",
                             {"category_id": "nonexistent-cat", "target": "codex"})
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        self.assertIn("nonexistent-cat", body["error"])


if __name__ == "__main__":
    unittest.main()
