"""Tests for sources/github_graphql.py. Run: python3 -m tests.test_graphql

不联网 — gh CLI 子进程全部 mock。契约：
  - 文档构造：N 个别名 search 字段、引号转义、first 参数
  - 节点解析：与 gh_search REST 输出同 shape（name/desc/url/stars/forks/lang/topics/updated/pushed）
  - 批量：去重、软失败（整批失败/部分别名 null → mapping 缺 key，不抛异常）
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.github_graphql import _build_document, _node_to_repo, gh_search_batch


NODE = {
    "nameWithOwner": "owner/repo",
    "description": " An AI tool ",
    "url": "https://github.com/owner/repo",
    "stargazerCount": 12345,
    "forkCount": 67,
    "primaryLanguage": {"name": "Python"},
    "repositoryTopics": {"nodes": [{"topic": {"name": "llm"}}, {"topic": {"name": "agent"}}]},
    "updatedAt": "2026-09-01T10:00:00Z",
    "pushedAt": "2026-09-02T10:00:00Z",
}


def test_build_document_aliases_and_escaping():
    doc = _build_document(['topic:ai-agent stars:>500', 'stars:>500 "AI agent" in:name'], 30)
    assert 'q0: search(query: "topic:ai-agent stars:>500", type: REPOSITORY, first: 30)' in doc
    # 双引号转义
    assert '\\"AI agent\\"' in doc
    assert "q1: search(" in doc
    assert "nameWithOwner" in doc and "stargazerCount" in doc


def test_node_to_repo_shape_matches_rest():
    r = _node_to_repo(NODE)
    assert r["name"] == "owner/repo"
    assert r["desc"] == "An AI tool"
    assert r["stars"] == 12345
    assert r["forks"] == 67
    assert r["lang"] == "Python"
    assert r["topics"] == ["llm", "agent"]
    assert r["updated"] == "2026-09-01"
    assert r["pushed"] == "2026-09-02"
    assert r["source"] == "gh_graphql"
    # 空 language / 空 topics 不炸
    bare = _node_to_repo({"nameWithOwner": "a/b"})
    assert bare["lang"] == "—" and bare["topics"] == []


def _gh_run(stdout_payload=None, returncode=0, stderr=""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = json.dumps(stdout_payload or {})
    m.stderr = stderr
    return m


def test_batch_success_and_dedupe():
    payload = {"data": {"q0": {"repos": [NODE]}, "q1": {"repos": [NODE]}}}
    with patch("sources.github_graphql.subprocess.run", return_value=_gh_run(payload)):
        # 重复 query 只执行一次 → 文档里只有 q0
        out = gh_search_batch(["topic:ai-agent stars:>500", "topic:ai-agent stars:>500"])
    assert list(out.keys()) == ["topic:ai-agent stars:>500"]
    assert out["topic:ai-agent stars:>500"][0]["name"] == "owner/repo"


def test_batch_partial_alias_null_recovered_by_sweep():
    # q1 别名失败（data.q1 = null）→ 补漏轮把该 query 单独重跑。
    # 静态 mock 下单别名文档读的是 q0（有数据）→ 补跑成功。
    payload = {"data": {"q0": {"repos": [NODE]}, "q1": None},
               "errors": [{"message": "partial"}]}
    with patch("sources.github_graphql.subprocess.run", return_value=_gh_run(payload)):
        out = gh_search_batch(["q one", "q two"], pace_s=0)
    assert "q one" in out and "q two" in out


def test_batch_persistent_null_stays_missing():
    # 别名恒为 null → 补漏轮也拿不到 → mapping 缺失，调用方回退 REST
    payload = {"data": {"q0": None, "q1": None}, "errors": [{"message": "bad"}]}
    with patch("sources.github_graphql.subprocess.run", return_value=_gh_run(payload)):
        out = gh_search_batch(["q one", "q two"], pace_s=0)
    assert out == {}


def test_batch_hard_failure_returns_empty_mapping():
    # 整批失败（非零退出码）→ 拆分重试全灭 → 空 mapping；调用方对缺失 query 回退 REST
    with patch(
        "sources.github_graphql.subprocess.run",
        return_value=_gh_run(returncode=1, stderr="gh: API rate limit exceeded"),
    ):
        out = gh_search_batch(["a", "b", "c"], pace_s=0, retries=0, max_rounds=2)
    assert out == {}


def test_batch_document_level_error_raises_then_soft_skips():
    # errors 且无 data → 抛 → gh_search_batch 捕获后跳过该批（软失败）
    payload = {"data": None, "errors": [{"message": "Bad credentials"}]}
    with patch("sources.github_graphql.subprocess.run", return_value=_gh_run(payload)):
        out = gh_search_batch(["a"], pace_s=0)
    assert out == {}


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
