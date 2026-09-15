"""Tests for 2026-09 crawl-coverage fixes. Run: python3 -m tests.test_crawl_sources

覆盖审核发现的 P0-P3 修复:
  P0  MCP registry 死源(mcp 分类 queries 非空 → source 分支不可达)
  P1  5k 池 GraphQL 腰斩(per_page 50 vs REST 100)+ TOP_5K_LIMIT 截断
  P1  低星新星通道缺失
  P2  去重键大小写
  P3  HF models 默认 sort / trending 兜底查询
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import radar  # noqa: E402
from sources.github_graphql import _build_document  # noqa: E402


# ── P0:MCP registry 死源 ──────────────────────────────────────────


def test_mcp_category_uses_registry_source():
    """mcp 分类必须 queries 为空(走 source 分支),否则 fetch_mcp_registry 不可达。"""
    cats = {c["id"]: c for c in radar.CATEGORIES}
    mcp = cats["mcp"]
    assert mcp.get("source") == "mcp_registry"
    assert not mcp.get("queries"), "queries 非空会让 source 分支永不执行(P0 复发)"


def test_mcp_dev_category_holds_github_queries():
    """原 9 条 GitHub MCP query 挪到 mcp_dev(而非丢弃)。"""
    cats = {c["id"]: c for c in radar.CATEGORIES}
    dev = cats["mcp_dev"]
    assert not dev.get("source")
    assert len(dev["queries"]) == 9


def test_all_sourced_categories_have_empty_queries():
    """所有 source 型分类(hf/arxiv/mcp)都必须 queries 为空 — 分发条件即此。"""
    for c in radar.CATEGORIES:
        if c.get("source"):
            assert not c.get("queries"), f"{c['id']}: source 与 queries 互斥"


# ── P1:5k 池 ─────────────────────────────────────────────────────


def test_top5k_limit_raised():
    """300 → 800:5k 池每天只有星标 top300 入 PG 的截断必须已放开。"""
    assert radar.TOP_5K_LIMIT >= 800


# ── P2:去重键大小写 ──────────────────────────────────────────────
# (merge 键小写化发生在 _crawl_inner 内联逻辑中 — 以行为级验证替代:normalize_git_url)


def test_normalize_git_url_lowercase_dedup():
    assert (
        radar.normalize_git_url("https://github.com/Owner/Repo/")
        == radar.normalize_git_url("https://github.com/owner/repo")
    )


# ── GraphQL 游标文档(P1 page2 基础)──────────────────────────────


def test_build_document_without_cursor():
    doc = _build_document(["topic:x stars:>1"], 30)
    assert 'q0: search(query: "topic:x stars:>1", type: REPOSITORY, first: 30)' in doc
    assert "after:" not in doc
    assert "pageInfo { endCursor hasNextPage }" in doc


def test_build_document_with_cursor():
    doc = _build_document(["topic:x stars:>1"], 30, cursors=["ABC=="])
    assert 'after: "ABC=="' in doc


def test_build_document_escapes_cursor_and_query():
    doc = _build_document(['q"uery'], 30, cursors=['CUR"SOR'])
    assert 'after: "CUR\\"SOR"' in doc


def test_gh_search_batch_follows_page2():
    """满页 query 用游标追第二页,合并去重。mock gh CLI。"""
    from sources import github_graphql as gg

    state = {"calls": 0}

    def fake_run(document, timeout=90):
        state["calls"] += 1
        if state["calls"] == 1:  # 第一页:满页 + hasNextPage
            data = {
                "q0": {
                    "repos": [
                        {"nameWithOwner": "a/r1", "stargazerCount": 5},
                        {"nameWithOwner": "a/r2", "stargazerCount": 6},
                    ],
                    "pageInfo": {"endCursor": "CUR1", "hasNextPage": True},
                }
            }
        else:  # 第二页
            data = {
                "q0": {
                    "repos": [
                        {"nameWithOwner": "a/r1", "stargazerCount": 5},  # 跨页重复
                        {"nameWithOwner": "a/r3", "stargazerCount": 7},
                    ],
                    "pageInfo": {"endCursor": "CUR2", "hasNextPage": True},
                }
            }
        return data

    with mock.patch.object(gg, "_run_gh_graphql", side_effect=fake_run):
        res = gg.gh_search_batch(
            ["topic:x stars:>1"], per_page=2, batch_size=6, follow_page2=True
        )
    names = [r["name"] for r in res["topic:x stars:>1"]]
    assert names == ["a/r1", "a/r2", "a/r3"], f"page2 应追加去重,got {names}"


def test_gh_search_batch_no_page2_when_not_full():
    """未满页(hasNextPage=False)不追页。"""
    from sources import github_graphql as gg

    def fake_run(document, timeout=90):
        return {
            "q0": {
                "repos": [{"nameWithOwner": "a/only", "stargazerCount": 1}],
                "pageInfo": {"endCursor": None, "hasNextPage": False},
            }
        }

    with mock.patch.object(gg, "_run_gh_graphql", side_effect=fake_run) as m:
        res = gg.gh_search_batch(["topic:x"], per_page=5, follow_page2=True)
    assert m.call_count == 1  # 没有第二次调用
    assert len(res["topic:x"]) == 1


# ── P3 ───────────────────────────────────────────────────────────


def test_hf_models_default_sort_is_likes7d():
    """实测 HF models API:trending 400,likes7d 有效且带 trendingScore。"""
    import inspect

    from sources.huggingface_models import VALID_SORTS, fetch_huggingface_models_trending

    sig = inspect.signature(fetch_huggingface_models_trending)
    assert sig.parameters["sort"].default == "likes7d"
    assert "trending" not in VALID_SORTS


def test_recent_active_fallback_uses_hard_topics():
    import inspect

    src = inspect.getsource(radar.fetch_recent_active_repos)
    assert "topic:ai-agent" in src
    # 裸 topic:ai(query 字符串里以 " 结尾)不得再出现 — 宽 topic 兜底白跑
    assert 'topic:ai"' not in src


def test_cat_pairs_filtered_to_persisted_before_replace():
    """外键回归:MCP registry 项被全局 dedup 丢弃后,其分类关联不得再进
    repo_categories(否则整库事务回滚 → JSON fallback)。"""
    import inspect

    src = inspect.getsource(radar._crawl_inner)
    assert "_persisted_names" in src
    assert "if n in _persisted_names" in src


if __name__ == "__main__":
    mod = sys.modules[__name__]
    failed = 0
    for name, fn in sorted(vars(mod).items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  ✗ {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
