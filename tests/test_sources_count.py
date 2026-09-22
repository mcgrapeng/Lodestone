"""Tests for /api/data sources field + data-provenance.json cross-check.

ponytail: 2026-09 FU-marquee — /api/data 必须返带 6 条 sources(name/label/count),
前端 Header marquee 据此循环显示 7 个来源徽标(本字段是数据来源,徽标还有
huggingface/mcp/arxiv/awesome_lists/hackernews_ai/github)。
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
PROV = DATA / "data-provenance.json"
BASE = "http://127.0.0.1:8765"


def _fetch_api_data(timeout: int = 15) -> dict:
    """GET /api/data — 该 endpoint 返回 ~1.4MB JSON,给 15s 余量。

    ponytail: 用户级 ~/.curlrc 注入了 -w "\\nHTTP %{http_code} (%{time_total}s)\\n",
    不指定 -o 时 curl 会把这段追加到 stdout — 我们的 JSON parse 会被尾部的
    "HTTP 200" 干扰。-w "" 是显式覆盖,curl 会用空串替掉 rc 的写格式,
    body 就干净了。
    """
    r = subprocess.run(
        ["curl", "-sS", "-w", "", BASE + "/api/data"],
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"server not reachable: {r.stderr}")
    return json.loads(r.stdout)


class SourcesCountTest(unittest.TestCase):
    """2026-09 FU-marquee: /api/data.sources shape + provenance 一致性。"""

    def test_api_data_has_sources(self):
        """/api/data 必须含 sources 数组,6 条命名 source 全在。"""
        d = _fetch_api_data()
        self.assertIn("sources", d)
        names = {s["name"] for s in d["sources"]}
        self.assertEqual(
            names,
            {"github", "huggingface", "mcp", "arxiv", "awesome_lists", "hackernews_ai"},
        )

    def test_each_source_has_count_label_name(self):
        """每条 source 必须有 {name, label, count:int>=0} 三个字段。"""
        d = _fetch_api_data()
        for s in d["sources"]:
            self.assertIn("name", s)
            self.assertIn("label", s)
            self.assertIn("count", s)
            self.assertIsInstance(s["count"], int)
            self.assertGreaterEqual(s["count"], 0)

    def test_provenance_matches_marquee(self):
        """data-provenance.json 的 sources_count 必须等于 /api/data 的 sources counts。"""
        d = _fetch_api_data()
        self.assertTrue(PROV.is_file(),
                        f"missing provenance file: {PROV}")
        prov = json.loads(PROV.read_text())
        api_counts = {s["name"]: s["count"] for s in d["sources"]}
        for name, count in prov["sources_count"].items():
            self.assertEqual(
                api_counts.get(name, 0), count,
                f"{name} count mismatch: api={api_counts.get(name, 0)} "
                f"vs provenance={count}",
            )


if __name__ == "__main__":
    unittest.main()
