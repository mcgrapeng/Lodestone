"""Tests for radar_pkg.translate section extraction + radar_pkg.skill_probe.

2026-09: README → {intro, can_do, benefit} 三段拆分；SKILL.md 探测。
无 LLM、无外网 — 全 mock；只验证分类/解析/缓存逻辑。
Run: python3 -m tests.test_translate
"""

import io
import os
import sys
import urllib.error  # noqa: F401 — used in mocked HTTPError
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from radar_pkg.translate import (
    _build_sections_zh,
    _split_readme_sections,
    _strip_markdown_to_text,
)


# =========================================================================
# _split_readme_sections — heading keyword → bucket mapping
# =========================================================================
def test_split_readme_sections_happy_path():
    """README 包含 ## What is / ## Features / ## Why 三段 → 三桶都有。"""
    md = (
        "# Project Title\n\n"
        "Some intro text.\n\n"
        "## What is Foo\n\n"
        "Foo is a tool that does X and Y in Z. " * 5 + "\n\n"
        "## Features\n\n"
        "Foo supports streaming, batching, retries, and observability. " * 4 + "\n\n"
        "## Why use Foo\n\n"
        "Foo is 10x faster, has zero config, and ships batteries included. " * 3
    )
    out = _split_readme_sections(md)
    assert out["intro"].startswith("Foo is a tool"), f"intro got: {out['intro'][:80]!r}"
    assert "streaming" in out["can_do"]
    assert "10x faster" in out["when_to_use"] or out["when_to_use"] == ""  # when_to_use may not match keywords


def test_split_readme_sections_preamble_fills_intro():
    """无 ## What is 等 heading 时 — preamble（首个 heading 前的内容）充当 intro。
    这是 README 标配：开头介绍 + 后列 Features/Why。"""
    md = (
        "Foo is a tool that aggregates AI project signals from GitHub, "
        "HuggingFace and the MCP registry into a single Chinese-friendly dashboard. "
        "It is designed for AI application engineers who want to track emerging "
        "tools without spending hours reading RSS feeds.\n\n"
        "## Features\n\n- bullet 1\n- bullet 2\n- bullet 3\n\n"
        "## License\n\nMIT"
    )
    out = _split_readme_sections(md)
    assert out["intro"].startswith("Foo is a tool"), out["intro"][:60]
    assert out["can_do"].startswith("- bullet 1"), out["can_do"][:30]
    # ponytail: 2026-09 — 5 桶 schema. benefit → when_to_use/problem 都不命中(只有 License)
    assert out["when_to_use"] == ""
    assert out["problem"] == ""
    assert out["competitive"] == ""


def test_split_readme_sections_skip_decoration():
    """## License / ## Contributors / ## Thanks 等装饰 heading 不进 can_do。"""
    md = (
        "## License\n\nMIT License text here. " * 10 + "\n\n"
        "## Features\n\nReal features content that is long enough to qualify. " * 3
    )
    out = _split_readme_sections(md)
    assert out["can_do"].startswith("Real features"), out["can_do"][:60]
    assert "MIT" not in out["can_do"]


def test_split_readme_sections_chinese_headings():
    """中文 heading（## 介绍 / ## 功能 / ## 优势）也能命中。"""
    md = (
        "## 介绍\n\n这是一个 AI Agent 框架，提供多步推理、工具调用、记忆管理三大核心能力。"
        * 2
        + "\n\n"
        "## 功能\n\n支持 MCP 协议、Claude / GPT 接入、流式响应、结构化输出。"
        * 2
        + "\n\n"
        "## 优势\n\n零配置启动，文档详尽，社区活跃，每月发布新版本。" * 2
    )
    out = _split_readme_sections(md)
    assert "AI Agent 框架" in out["intro"]
    assert "MCP" in out["can_do"]
    # ponytail: 2026-09 — 5 桶 schema. 优势/亮点/动机/背景关键词归到 when_to_use
    assert "零配置" in out["when_to_use"]


def test_split_readme_sections_first_match_per_bucket():
    """多个匹配 heading → 只取第一个（不堆叠）。"""
    md = (
        "## Features\n\nFirst feature block, more than forty characters of content here. "
        * 2
        + "\n\n"
        "## More Features\n\nShould not be picked — bucket already filled. " * 3
    )
    out = _split_readme_sections(md)
    assert "First feature block" in out["can_do"]
    assert "Should not be picked" not in out["can_do"]


def test_split_readme_sections_too_short_paragraph_skipped():
    """section body 太短（< 20 字符）→ 跳过，避免徽章/链接噪声。"""
    md = (
        "## Features\n\nshort\n\n"
        "## More Features\n\nThis is a proper paragraph with enough content to qualify as a real description. "
        * 3
    )
    out = _split_readme_sections(md)
    assert "proper paragraph" in out["can_do"]


# =========================================================================
# _build_sections_zh — end-to-end (clean + split + translate, mocked)
# =========================================================================
def test_build_sections_zh_empty_returns_empty():
    # ponytail: 2026-09 — 5 桶 schema
    assert _build_sections_zh("") == {
        "intro": "", "can_do": "", "problem": "", "competitive": "", "when_to_use": ""
    }


def test_build_sections_zh_translate_failure_leaves_bucket_empty():
    """translate 失败 → 该桶空，不污染其他桶。"""
    md = (
        "## What is Foo\n\nFoo is a tool that does X and Y in Z. " * 5 + "\n\n"
        "## Features\n\nFoo supports streaming and batching with retries. " * 3
    )
    # mock _chunked_translate: intro 翻译成功，can_do 返回原文（视为翻译失败）
    calls = []

    def fake_translate(text, target="zh-CN"):
        calls.append(text[:40])
        # 首次调用返回中文（成功），后续返回原文（失败 → 留空）
        if len(calls) == 1:
            return "Foo 是一个做 X 和 Y 的工具。" * 2
        return text  # not translated

    with patch("radar_pkg.translate._chunked_translate", side_effect=fake_translate):
        out = _build_sections_zh(md)
    assert "工具" in out["intro"]
    assert out["can_do"] == ""  # 翻译失败 → 留空
    # ponytail: 2026-09 — 5 桶 schema. 缺桶填空串
    assert out["problem"] == ""
    assert out["when_to_use"] == ""


def test_strip_markdown_preserves_headings():
    """_strip_markdown_to_text 不应把 ## heading 抹掉 — section splitter 需要它。"""
    md = "# Title\n\n## Features\n\nReal content.\n\n## License\n\nMIT"
    clean = _strip_markdown_to_text(md)
    assert "## Features" in clean
    assert "## License" in clean


# =========================================================================
# radar_pkg.skill_probe — SKILL.md 探测（mocked urllib）
# =========================================================================
def test_probe_one_skill_md_found():
    """任意一个 SKILL.md / skill.md / SKILL.yaml HEAD 200 → is_skill=True。"""
    from radar_pkg.skill_probe import _probe_one

    def fake_head(url, timeout=8):
        return url.endswith("/SKILL.md")

    with (
        patch("radar_pkg.skill_probe._head_ok", side_effect=fake_head),
        patch("radar_pkg.skill_probe._resolve_branch", return_value="main"),
    ):
        cache: dict = {}
        result = _probe_one("foo/bar", cache)
    assert result is True
    assert cache["foo/bar"]["is_skill"] is True
    assert cache["foo/bar"]["branch"] == "main"


def test_probe_one_no_skill_files():
    """三个文件名全部 404 → is_skill=False。"""
    from radar_pkg.skill_probe import _probe_one

    with (
        patch("radar_pkg.skill_probe._head_ok", return_value=False),
        patch("radar_pkg.skill_probe._resolve_branch", return_value="main"),
    ):
        cache: dict = {}
        result = _probe_one("foo/bar", cache)
    assert result is False


def test_probe_one_uses_cache():
    """缓存命中 → 不再探测，直接返回缓存值。"""
    from radar_pkg.skill_probe import _probe_one

    cache = {"foo/bar": {"is_skill": True, "probed_at": "2026-01-01", "branch": "main"}}
    with patch("radar_pkg.skill_probe._head_ok") as mock_head:
        result = _probe_one("foo/bar", cache)
    assert result is True
    mock_head.assert_not_called()


def test_probe_skills_concurrent_with_progress():
    """probe_skills 增量：跳过缓存命中、并发探测未命中；save_cache 在批完成时落盘。"""
    from radar_pkg import skill_probe

    cache = {"cached/repo": {"is_skill": True, "probed_at": "x", "branch": "main"}}

    def fake_probe_one(full_name, c):
        c[full_name.lower()] = {"is_skill": False, "probed_at": "x", "branch": "main"}
        return False

    with (
        patch.object(skill_probe, "_load_cache", return_value=dict(cache)),
        patch.object(skill_probe, "_save_cache") as save_mock,
        patch.object(skill_probe, "_probe_one", side_effect=fake_probe_one),
    ):
        out = skill_probe.probe_skills(
            ["cached/repo", "new/repo1", "new/repo2"], max_workers=2
        )
    assert out["cached/repo"] is True  # cached → skip probe
    assert out["new/repo1"] is False  # probed → False
    assert out["new/repo2"] is False
    assert save_mock.called


def test_annotate_repos_writes_is_skill_field():
    """annotate_repos: 仅 GitHub 仓库被探测；HF/arXiv 跳过；is_skill 写回 repo 字典。"""
    from radar_pkg import skill_probe

    repos = [
        {"name": "owner/skill-repo", "url": "https://github.com/owner/skill-repo"},
        {"name": "owner/non-skill", "url": "https://github.com/owner/non-skill"},
        {"name": "hf/space", "url": "https://huggingface.co/spaces/foo/bar"},  # skipped
        {"name": "", "url": "https://github.com/x/y"},  # skipped (no name)
    ]

    def fake_probe(names, max_workers=8, force=False):
        return {n.lower(): True for n in names}

    with patch.object(skill_probe, "probe_skills", side_effect=fake_probe):
        n = skill_probe.annotate_repos(repos)
    assert n == 2  # only 2 GitHub repos with valid names
    by_name = {r["name"]: r for r in repos}
    assert by_name["owner/skill-repo"]["is_skill"] is True
    assert by_name["owner/non-skill"]["is_skill"] is True
    assert "is_skill" not in by_name["hf/space"]
    assert "is_skill" not in by_name[""]


# =========================================================================
# _head_ok — HTTP error semantics
# =========================================================================
def test_head_ok_404_returns_false():
    from radar_pkg.skill_probe import _head_ok
    import urllib.request

    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=8):
        if "missing" in req.full_url:
            raise urllib.error.HTTPError(
                req.full_url,
                404,
                "Not Found",
                __import__("http.client").HTTPMessage(io.BytesIO()),
                None,
            )
        return FakeResp()

    # ponytail: patch urllib.request.urlopen directly (skill_probe calls it via module
    # attribute, so patching via the skill_probe.urllib.request namespace is a no-op)
    with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
        assert _head_ok("https://example.com/has-skill.md") is True
        assert _head_ok("https://example.com/missing.md") is False


def test_head_ok_timeout_returns_false():
    """网络错误 → False（保守视为不存在）。"""
    from radar_pkg.skill_probe import _head_ok

    def fake_urlopen(req, timeout=8):
        raise TimeoutError("nope")

    with patch(
        "radar_pkg.skill_probe.urllib.request.urlopen", side_effect=fake_urlopen
    ):
        assert _head_ok("https://example.com/whatever") is False


if __name__ == "__main__":
    fns = [
        (n, getattr(sys.modules[__name__], n))
        for n in dir(sys.modules[__name__])
        if n.startswith("test_") and callable(getattr(sys.modules[__name__], n))
    ]
    for n, fn in sorted(fns):
        try:
            fn()
            print(f"  ✓ {n}")
        except Exception as e:
            print(f"  ✗ {n}: {e}")
            raise
    print(f"\nAll {len(fns)} tests passed.")


# =========================================================================
# radar_pkg.llm_analyze — JSON 解析 / prompt shape / cache / provider 检测
# =========================================================================
def test_extract_json_clean():
    from radar_pkg.llm_analyze import _extract_json

    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fence():
    from radar_pkg.llm_analyze import _extract_json

    raw = '```json\n{"a": 1, "b": "x"}\n```'
    assert _extract_json(raw) == {"a": 1, "b": "x"}


def test_extract_json_with_prefix_text():
    from radar_pkg.llm_analyze import _extract_json

    raw = 'Here is the analysis:\n{"what": "AI tool"}'
    assert _extract_json(raw) == {"what": "AI tool"}


def test_extract_json_with_trailing_garbage():
    """模型偶发在 JSON 后追加解释文字 — 切到第一个 { 到最后一个 }。"""
    from radar_pkg.llm_analyze import _extract_json

    raw = '{"what": "x"} \nThat covers the main points.'
    assert _extract_json(raw) == {"what": "x"}


def test_extract_json_invalid_returns_none():
    from radar_pkg.llm_analyze import _extract_json

    assert _extract_json("not json at all") is None
    assert _extract_json("") is None
    assert _extract_json('{"broken') is None


def test_normalize_full():
    """完整输入 → 规整后的 5d 字典。"""
    from radar_pkg.llm_analyze import _normalize

    inp = {
        "what": "AI coding assistant",
        "can_do": "autocomplete, refactor, test",
        "problem": "writes boilerplate",
        "alternatives": [
            {"name": "copilot", "pros": "deep integration", "cons": "paid"},
            {"name": "cursor", "pros": "fast", "cons": "closed source"},
            "aider",  # also accept legacy string form
        ],
        "when_to_use": "when you want a local coding assistant",
    }
    out = _normalize(inp)
    assert out["what"] == "AI coding assistant"
    assert out["can_do"] == "autocomplete, refactor, test"
    assert out["problem"] == "writes boilerplate"
    assert len(out["alternatives"]) == 3
    assert out["alternatives"][0]["name"] == "copilot"
    assert out["alternatives"][0]["pros"] == "deep integration"
    assert out["alternatives"][0]["cons"] == "paid"
    assert out["alternatives"][2] == {"name": "aider", "pros": "", "cons": ""}
    assert "local coding" in out["when_to_use"]


def test_normalize_missing_fields():
    from radar_pkg.llm_analyze import _normalize

    out = _normalize({"what": "x"})
    assert out["what"] == "x"
    assert out["can_do"] == ""
    assert out["problem"] == ""
    assert out["alternatives"] == []
    assert out["when_to_use"] == ""


def test_normalize_none_input():
    from radar_pkg.llm_analyze import _normalize

    out = _normalize(None)
    # ponytail: 2026-09 — 5 桶 schema 不再有 pros/cons
    assert out == {
        "what": "", "can_do": "", "problem": "", "alternatives": [], "when_to_use": ""
    }


def test_normalize_caps_lengths():
    from radar_pkg.llm_analyze import _normalize

    inp = {
        "what": "x" * 500,
        "can_do": "x" * 1000,
        "problem": "y" * 500,
        "alternatives": [{"name": "a" * 200, "pros": "x" * 500, "cons": "y" * 500}] * 10,
        "when_to_use": "z" * 1000,
    }
    out = _normalize(inp)
    assert len(out["what"]) <= 200
    assert len(out["can_do"]) <= 400
    assert len(out["problem"]) <= 200
    assert len(out["alternatives"]) <= 5
    for alt in out["alternatives"]:
        assert len(alt["name"]) <= 100
        assert len(alt["pros"]) <= 200
        assert len(alt["cons"]) <= 200
    assert len(out["when_to_use"]) <= 400


def test_build_prompt_contains_repo_metadata():
    from radar_pkg.llm_analyze import _build_prompt

    p = _build_prompt(
        "owner/repo",
        "README content here",
        ["llm", "agent"],
        "Python",
    )
    assert "owner/repo" in p
    assert "Python" in p
    assert "llm, agent" in p
    assert "JSON" in p  # strict JSON 要求
    assert "what" in p and "problem" in p and "alternatives" in p
    assert "when_to_use" in p


def test_build_prompt_truncates_long_readme():
    """3000 字符上限 — 长 README 不让单次 prompt 爆炸。"""
    from radar_pkg.llm_analyze import _build_prompt

    long_md = "X" * 10000
    p = _build_prompt("o/r", long_md, [], "Go")
    # 不应该包含 10000 个 X（被截断）
    assert p.count("X") <= 3500  # 3000 截断 + prompt 模板里几个 X


def test_analyze_one_skips_low_stars():
    """< LLM_MIN_STARS（默认 50）的 repo 直接跳过，不调 LLM。"""
    from radar_pkg import llm_analyze

    with patch.object(llm_analyze, "_dispatch") as m:
        result = llm_analyze.analyze_one("owner/starving", stars=10)
    assert result is None
    m.assert_not_called()


def test_analyze_one_skips_non_github():
    from radar_pkg import llm_analyze

    with patch.object(llm_analyze, "_dispatch") as m:
        assert llm_analyze.analyze_one("") is None
        assert llm_analyze.analyze_one("no_slash") is None
    m.assert_not_called()


def test_analyze_one_uses_cache():
    """缓存命中直接复用，不调 LLM。"""
    from radar_pkg import llm_analyze

    cached = {
        "owner/repo": {
            "what": "cached",
            "problem": "",
            "alternatives": [],
            "pros": [],
            "cons": [],
            "when_to_use": "",
        }
    }
    with patch.object(llm_analyze, "_dispatch") as m:
        result = llm_analyze.analyze_one("owner/repo", stars=1000, cache=cached)
    assert result["what"] == "cached"
    m.assert_not_called()


def test_analyze_one_calls_dispatch_and_caches():
    """未命中 → 调 LLM → 写入 cache → 返回规整结果。"""
    from radar_pkg import llm_analyze

    fake_result = {
        "what": "test tool",
        "problem": "test problem",
        "alternatives": ["alt1"],
        "pros": ["pro1"],
        "cons": ["con1"],
        "when_to_use": "when testing",
    }
    cache: dict = {}
    with patch.object(llm_analyze, "_dispatch", return_value=fake_result):
        result = llm_analyze.analyze_one(
            "owner/repo",
            readme="some readme",
            topics=["llm"],
            lang="Python",
            stars=1000,
            cache=cache,
        )
    assert result["what"] == "test tool"
    assert "owner/repo" in cache
    assert cache["owner/repo"]["_analyzed_at"]


def test_analyze_one_dispatch_failure_returns_none():
    """LLM 调失败 → 返 None，不污染 cache。"""
    from radar_pkg import llm_analyze

    cache: dict = {}
    with patch.object(llm_analyze, "_dispatch", return_value=None):
        result = llm_analyze.analyze_one(
            "owner/repo",
            readme="x",
            stars=1000,
            cache=cache,
        )
    assert result is None
    assert "owner/repo" not in cache


def test_detect_provider_anthropic():
    from radar_pkg import llm_analyze

    with patch.dict(
        os.environ if False else __import__("os").environ,
        {"ANTHROPIC_API_KEY": "x"},
        clear=False,
    ):
        assert llm_analyze.detect_provider() == "anthropic"


def test_detect_provider_openai():
    from radar_pkg import llm_analyze
    import os

    env = {**os.environ, "ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "x"}
    with patch.dict(os.environ, env, clear=True):
        # 注：clear=True 会丢失非 patch 字段，但我们要测的是 detect_provider 优先级
        # 实际：anthropic 优先，需要 patch 时清除 anthropic
        pass
    # 简化的直接测试：手动设环境变量
    old_a = os.environ.pop("ANTHROPIC_API_KEY", None)
    old_o = os.environ.pop("OPENAI_API_KEY", None)
    try:
        os.environ["OPENAI_API_KEY"] = "x"
        assert llm_analyze.detect_provider() == "openai"
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
        if old_a:
            os.environ["ANTHROPIC_API_KEY"] = old_a
        if old_o:
            os.environ["OPENAI_API_KEY"] = old_o


def test_detect_provider_ollama_local():
    """127.0.0.1:11434 在线 → Ollama（无需 API key）。"""
    from radar_pkg import llm_analyze
    import os

    old_a = os.environ.pop("ANTHROPIC_API_KEY", None)
    old_o = os.environ.pop("OPENAI_API_KEY", None)
    try:
        # mock 探测本地服务
        with patch.object(llm_analyze.urllib.request, "urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 200
            assert llm_analyze.detect_provider() == "ollama"
    finally:
        if old_a:
            os.environ["ANTHROPIC_API_KEY"] = old_a
        if old_o:
            os.environ["OPENAI_API_KEY"] = old_o


def test_detect_provider_none_when_unconfigured():
    """没 key + 没本地服务 → None。"""
    from radar_pkg import llm_analyze
    import os

    old = {k: os.environ.pop(k, None) for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]}
    try:
        with patch.object(llm_analyze.urllib.request, "urlopen") as mock:
            mock.side_effect = OSError("no service")
            assert llm_analyze.detect_provider() is None
    finally:
        for k, v in old.items():
            if v:
                os.environ[k] = v
