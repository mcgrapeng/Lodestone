"""stdlib-only tests for radar.py. Run: python3 -m tests.test_radar"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Make sibling radar.py importable
sys.path.insert(0, str(Path(__file__).parent.parent))
import radar


def _platforms_at(tmp: Path) -> dict:
    """2026-09: detect/install 的平台目录来自 _SKILL_PLATFORM_PATHS(模块加载时
    已展开为绝对路径),patch Path.home 不再影响 — 测试需显式重定向平台表,
    否则 symlink/扫描会写真实 ~/.claude/skills。"""
    return {
        "claude": str(tmp / ".claude" / "skills"),
        "codex": str(tmp / ".codex" / "skills"),
        "opencode": str(tmp / ".config" / "opencode" / "skills"),
    }


def test_install_skill_from_github_accepts_owner_repo():
    """Bug: name='obra/superpowers' was rejected by old alnum-only check.

    ponytail: 2026-08 — install_skill_from_github now returns a dict
    {targets, cache_path} instead of a single path string.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache = tmp / "cache"
        with (
            patch("radar_pkg.core.SKILLS_CACHE", cache),
            patch("radar_pkg.core.SKILL_ORIGINS", cache.parent / "origins.json"),
            patch("radar.Path.home", return_value=tmp),
            patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", _platforms_at(tmp)),
        ):
            with patch("radar_pkg.install.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                # Pre-create the cache target so the function skips git clone
                target = cache / "superpowers"
                target.mkdir(parents=True)
                result = radar.install_skill_from_github(
                    "obra/superpowers", "https://github.com/obra/superpowers"
                )
                # 2026-08 — dict return with cache + targets
                assert isinstance(result, dict)
                assert str(result.get("cache", "")).endswith("superpowers")
                assert "targets" in result
                # Sidecar must be written
                origins = json.loads((cache.parent / "origins.json").read_text())
                assert origins["skills"]["superpowers"]["owner"] == "obra"
                assert (
                    origins["skills"]["superpowers"]["url"]
                    == "https://github.com/obra/superpowers"
                )


def test_install_skill_from_github_rejects_bad_name():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache = tmp / "cache"
        with (
            patch("radar_pkg.core.SKILLS_CACHE", cache),
            patch("radar.Path.home", return_value=tmp),
        ):
            try:
                radar.install_skill_from_github(
                    "evil;rm -rf /", "https://github.com/foo/bar"
                )
                assert False, "should have raised"
            except ValueError as e:
                assert "invalid" in str(e).lower()


def test_install_skill_rejects_url_name_mismatch():
    """Clone-under-trusted-name guard: url path must equal owner/repo."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with (
            patch("radar_pkg.core.SKILLS_CACHE", tmp / "cache"),
            patch("radar.Path.home", return_value=tmp),
        ):
            try:
                radar.install_skill_from_github(
                    "obra/superpowers", "https://github.com/evil/not-superpowers"
                )
                assert False, "should have raised"
            except ValueError as e:
                assert "does not match" in str(e)


def test_detect_local_skills_enriches_from_repo_index():
    """When a local skill's bare name matches a repo in the PG index, enrich with
    url/desc_zh/topics/stars (source: 'cache')."""
    index = {
        "superpowers": {
            "name": "obra/superpowers",
            "url": "https://github.com/obra/superpowers",
            "desc_zh": "代理技能框架",
            "description": "agentic skills framework",
            "topics": ["ai", "sdlc"],
            "stars": 2576,
            "best_category": "agent",
        }
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        skills_dir = tmp / ".claude" / "skills" / "superpowers"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\nname: superpowers\n---\n")
        with (
            patch("radar.Path.home", return_value=tmp),
            patch("radar_pkg.detect._load_repo_index", return_value=index),
            patch("radar_pkg.core.SKILL_ORIGINS", tmp / "origins.json"),
            patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", _platforms_at(tmp)),
        ):
            radar.invalidate_local_scan()
            result = radar.detect_local_skills()
            meta = result["skills"]["superpowers"]
            assert meta["url"] == "https://github.com/obra/superpowers"
            assert meta["desc_zh"] == "代理技能框架"
            assert meta["source"] == "cache"
            assert meta["stars"] == 2576


def test_detect_local_skills_falls_back_to_skill_md():
    """When no index/origin match, read SKILL.md frontmatter description."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        skills_dir = tmp / ".claude" / "skills" / "custom-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: custom\ndescription: My custom skill\n---\n"
        )
        with (
            patch("radar.Path.home", return_value=tmp),
            patch("radar_pkg.detect._load_repo_index", return_value={}),
            patch("radar_pkg.core.SKILL_ORIGINS", tmp / "origins.json"),
            patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", _platforms_at(tmp)),
            patch(
                "radar_pkg.detect.translate_batch", return_value={"custom-skill": "我的自定义技能"}
            ),
        ):
            radar.invalidate_local_scan()
            result = radar.detect_local_skills()
            meta = result["skills"]["custom-skill"]
            assert meta["source"] == "skillmd"
            assert meta["desc_en"] == "My custom skill"
            assert meta["desc_zh"] == "我的自定义技能"
            assert meta["url"] is None


def test_detect_local_skills_translates_desc_en_when_no_zh():
    """When desc_en is set but desc_zh is missing, detect_local_skills
    auto-translates desc_en via translate_batch so user sees Chinese."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        skills_dir = tmp / ".claude" / "skills" / "english-only-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: english-only\ndescription: An entirely English description\n---\n"
        )
        with (
            patch("radar.Path.home", return_value=tmp),
            patch("radar_pkg.detect._load_repo_index", return_value={}),
            patch("radar_pkg.core.SKILL_ORIGINS", tmp / "origins.json"),
            patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", _platforms_at(tmp)),
            patch(
                "radar_pkg.detect.translate_batch",
                return_value={"english-only-skill": "完全中文的描述"},
            ) as mock_tb,
        ):
            radar.invalidate_local_scan()
            result = radar.detect_local_skills()
            meta = result["skills"]["english-only-skill"]
            mock_tb.assert_called_once()
            call_pairs = mock_tb.call_args[0][0]
            assert (
                "english-only-skill",
                "An entirely English description",
            ) in call_pairs
            assert meta["desc_zh"] == "完全中文的描述"
            assert meta["desc_en"] == "An entirely English description"


def test_is_ai_relevant_requires_hard_topic():
    """Bare 'ai' topic must NOT pass (caught dbeaver/netdata); hard topics pass."""
    assert radar.is_ai_relevant({"name": "x/y", "topics": ["llm"]}) is True
    assert radar.is_ai_relevant({"name": "x/y", "topics": ["ai", "python"]}) is False
    assert radar.is_ai_relevant({"name": "x/y", "topics": ["mcp-server"]}) is True


def test_is_ai_relevant_text_hint_fallback():
    """No qualifying topics but name/description carries a strong AI phrase → pass."""
    assert (
        radar.is_ai_relevant(
            {
                "name": "foo/assistant",
                "topics": [],
                "description": "A personal AI assistant with memory",
            }
        )
        is True
    )
    # 'ai' inside words like 'email'/'main' must NOT match
    assert (
        radar.is_ai_relevant(
            {
                "name": "foo/mailqueue",
                "topics": [],
                "description": "email queue for main server",
            }
        )
        is False
    )


def test_is_ai_relevant_blocklist():
    """Stock/trading/crypto noise is dropped even with AI topics."""
    assert (
        radar.is_ai_relevant(
            {
                "name": "evil/stock-bot",
                "topics": ["ai-agent", "stock", "trading"],
            }
        )
        is False
    )
    assert (
        radar.is_ai_relevant(
            {
                "name": "good/claude-skills",
                "topics": ["ai-agent", "claude-code"],
            }
        )
        is True
    )


def test_crawl_lock_serializes():
    """acquire → second acquire fails → release → acquire works again."""
    with tempfile.TemporaryDirectory() as tmp:
        lock = Path(tmp) / "crawl.lock"
        with patch.object(radar, "CRAWL_LOCK", lock):
            assert radar.acquire_crawl_lock() is True
            assert radar.crawl_lock_held() is True
            assert radar.acquire_crawl_lock() is False  # second crawl rejected
            radar.release_crawl_lock()
            assert radar.crawl_lock_held() is False
            assert radar.acquire_crawl_lock() is True
            radar.release_crawl_lock()


def test_crawl_lock_stale_is_preempted():
    """A lock file older than the staleness window is treated as crash residue."""
    import os

    with tempfile.TemporaryDirectory() as tmp:
        lock = Path(tmp) / "crawl.lock"
        lock.write_text("123")
        old = radar.time.time() - radar.CRAWL_LOCK_STALE_S - 60
        os.utime(lock, (old, old))
        with patch.object(radar, "CRAWL_LOCK", lock):
            assert radar.crawl_lock_held() is False
            assert radar.acquire_crawl_lock() is True  # stale lock preempted
            radar.release_crawl_lock()


def test_repo_slug_from_url():
    f = radar._repo_slug_from_url
    assert f("https://github.com/owner/repo") == "owner/repo"
    assert f("https://github.com/owner/repo.git") == "owner/repo"
    assert f("https://github.com/owner") == ""
    assert f("https://gitlab.com/owner/repo") == ""
    assert f(None) == ""


def test_top_5k_plus_data_shape():
    """Verify the data shape the /api/top fallback pagination depends on."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        repos = [
            {
                "name": f"owner/repo{i}",
                "desc": "",
                "url": f"https://github.com/owner/repo{i}",
                "stars": 10000 - i,
                "lang": "Python",
                "topics": ["ai"],
                "pushed": "2026-07-20",
                "desc_zh": "",
                "facts": "",
                "local_installed": False,
            }
            for i in range(25)
        ]
        # Pagination math
        size = 10
        assert len(repos[0:size]) == 10
        assert len(repos[20:30]) == 5  # last partial page
        # Sort keys
        by_name = sorted(repos, key=lambda r: r["name"].lower())
        assert by_name[0]["name"] == "owner/repo0"
        by_recent = sorted(repos, key=lambda r: r.get("pushed", ""), reverse=True)
        assert by_recent[0]["pushed"] == "2026-07-20"


def test_is_ai_relevant_blocks_finance_domain():
    """产品定位 = AI 应用开发雷达：股票/金融/交易类一律排除（即使 AI 驱动）。"""
    trading_agents = {
        "name": "TauricResearch/TradingAgents",
        "desc": "Multi-agent LLM trading framework",
        "topics": ["finance", "trading", "llm", "multi-agent"],
    }
    assert radar.is_ai_relevant(trading_agents) is False

    finrobot = {
        "name": "AI4Finance-Foundation/FinRobot",
        "desc": "AI agent for financial markets",
        "topics": ["finance", "agent"],
    }
    assert radar.is_ai_relevant(finrobot) is False

    # 描述级短语（没有 blocklist topic 也能拦）
    desc_only = {
        "name": "x/QuantTrader",
        "desc": "LLM-powered algorithmic trading system",
        "topics": ["llm"],
    }
    assert radar.is_ai_relevant(desc_only) is False


def test_is_ai_relevant_no_finance_false_positives():
    """quantization / quantum 等含 quant 的 AI 术语不得误伤。"""
    llama_factory = {
        "name": "hiyouga/LlamaFactory",
        "desc": "Unified fine-tuning of LLMs",
        "topics": ["quantization", "llm", "fine-tuning"],
    }
    assert radar.is_ai_relevant(llama_factory) is True

    quantum = {"name": "QuantumNous/new-api", "desc": "LLM API gateway", "topics": ["llm"]}
    assert radar.is_ai_relevant(quantum) is True


def test_finance_block_sparing_for_category_results():
    """分类路径只用 is_finance_blocked（query 本身是 AI 信号）—
    Qwen-VL / playwright-mcp 这类 topics 变体不在 AI_TOPIC_HARD 的正经项目不被误伤。"""
    qwen_vl = {
        "name": "QwenLM/Qwen-VL",
        "desc": "The official repo of Qwen-VL chat & pretrained large vision language model",
        "topics": ["large-language-models", "vision-language-model"],
    }
    assert radar.is_finance_blocked(qwen_vl) is False

    pw_mcp = {
        "name": "microsoft/playwright-mcp",
        "desc": "Playwright MCP server",
        "topics": ["mcp", "playwright"],
    }
    assert radar.is_finance_blocked(pw_mcp) is False

    trading = {
        "name": "TauricResearch/TradingAgents",
        "desc": "Multi-agent LLM trading framework",
        "topics": ["finance", "trading"],
    }
    assert radar.is_finance_blocked(trading) is True


def test_normalize_git_url_dedup_key():
    """去重规则 = git 完整仓库地址：大小写/.git/尾斜杠/www 变体归并为同一键。"""
    f = radar.normalize_git_url
    assert f("https://github.com/Owner/Repo") == f("https://www.github.com/owner/repo/")
    assert f("https://github.com/owner/repo.git") == f("gh://owner/repo")
    assert f("https://github.com/Owner/Repo") == "gh://owner/repo"
    # 非 GitHub 地址保持域名区分
    assert f("https://huggingface.co/spaces/a/b") == "https://huggingface.co/spaces/a/b"
    assert f("") == ""


if __name__ == "__main__":
    for name, fn in sorted(
        {
            k: v
            for k, v in list(globals().items())
            if k.startswith("test_") and callable(v)
        }.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
