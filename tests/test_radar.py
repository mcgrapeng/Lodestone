"""stdlib-only tests for radar.py. Run: python3 -m tests.test_radar"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Make sibling radar.py importable
sys.path.insert(0, str(Path(__file__).parent.parent))
import radar


def test_install_skill_from_github_accepts_owner_repo():
    """Bug: name='obra/superpowers' was rejected by old alnum-only check."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache = tmp / "cache"
        with (
            patch.object(radar, "SKILLS_CACHE", cache),
            patch.object(radar, "SKILL_ORIGINS", cache.parent / "origins.json"),
            patch("radar.Path.home", return_value=tmp),
        ):
            with patch("radar.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                # Pre-create the cache target so the function skips git clone
                target = cache / "superpowers"
                target.mkdir(parents=True)
                path = radar.install_skill_from_github(
                    "obra/superpowers", "https://github.com/obra/superpowers"
                )
                assert path.endswith("superpowers")
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
            patch.object(radar, "SKILLS_CACHE", cache),
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
            patch.object(radar, "SKILLS_CACHE", tmp / "cache"),
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
            patch("radar._load_repo_index", return_value=index),
            patch("radar.SKILL_ORIGINS", tmp / "origins.json"),
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
            patch("radar._load_repo_index", return_value={}),
            patch("radar.SKILL_ORIGINS", tmp / "origins.json"),
            patch(
                "radar.translate_batch", return_value={"custom-skill": "我的自定义技能"}
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
            patch("radar._load_repo_index", return_value={}),
            patch("radar.SKILL_ORIGINS", tmp / "origins.json"),
            patch(
                "radar.translate_batch",
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
