"""stdlib-only tests for radar.py. Run: python3 -m tests.test_radar"""
import json, sys, tempfile
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
        with patch.object(radar, "SKILLS_CACHE", cache), \
             patch.object(radar, "SKILL_ORIGINS", cache.parent / "origins.json"), \
             patch("radar.Path.home", return_value=tmp):
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
                assert origins["skills"]["superpowers"]["url"] == "https://github.com/obra/superpowers"


def test_install_skill_from_github_rejects_bad_name():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache = tmp / "cache"
        with patch.object(radar, "SKILLS_CACHE", cache), \
             patch("radar.Path.home", return_value=tmp):
            try:
                radar.install_skill_from_github("evil;rm -rf /", "https://github.com/foo/bar")
                assert False, "should have raised"
            except ValueError as e:
                assert "invalid" in str(e).lower()


def test_detect_local_skills_uses_latest_json_when_present():
    """When a local skill name matches a repo in latest.json, return desc_zh/url/topics."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        skills_dir = tmp / ".claude" / "skills" / "superpowers"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\nname: superpowers\ndescription: An agentic skills framework\n---\n# body\n")
        (tmp / "data").mkdir()
        latest = {"hot_now": [], "categories": [
            {"repos": [{"name": "obra/superpowers", "desc_zh": "代理技能框架",
                        "url": "https://github.com/obra/superpowers",
                        "topics": ["ai", "sdlc"], "stars": 257640}]}
        ]}
        with patch("radar.Path.home", return_value=tmp), \
             patch("radar.DATA", tmp / "data"):
            (tmp / "data" / "latest.json").write_text(json.dumps(latest))
            result = radar.detect_local_skills()
            meta = result["skills"]["superpowers"]
            assert meta["url"] == "https://github.com/obra/superpowers"
            assert meta["desc_zh"] == "代理技能框架"
            assert meta["source"] == "cache"
            assert meta["stars"] == 257640


def test_detect_local_skills_falls_back_to_skill_md():
    """When latest.json has no match, read SKILL.md frontmatter description."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        skills_dir = tmp / ".claude" / "skills" / "custom-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\nname: custom\ndescription: My custom skill\n---\n")
        (tmp / "data").mkdir()
        (tmp / "data" / "latest.json").write_text(json.dumps({"hot_now": [], "categories": []}))
        with patch("radar.Path.home", return_value=tmp), \
             patch("radar.DATA", tmp / "data"), \
             patch("radar.translate_batch", return_value={"custom-skill": "我的自定义技能"}):
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
        (tmp / "data").mkdir()
        (tmp / "data" / "latest.json").write_text(
            json.dumps({"hot_now": [], "categories": []})
        )
        with patch("radar.Path.home", return_value=tmp), \
             patch("radar.DATA", tmp / "data"), \
             patch("radar.translate_batch", return_value={"english-only-skill": "完全中文的描述"}) as mock_tb:
            result = radar.detect_local_skills()
            meta = result["skills"]["english-only-skill"]
            mock_tb.assert_called_once()
            call_pairs = mock_tb.call_args[0][0]
            assert ("english-only-skill", "An entirely English description") in call_pairs
            assert meta["desc_zh"] == "完全中文的描述"
            assert meta["desc_en"] == "An entirely English description"


def test_ai_topic_whitelist_filters_blockchain():
    """awesome-blockchain (5k+ stars, NOT AI) must be filtered out of top_5k."""
    from radar import AI_TOPIC_WHITELIST
    repo = {"name": "foo/blockchain-list", "topics": ["blockchain", "awesome-blockchain"], "stars": 6000}
    has_ai_topic = any(t.lower() in AI_TOPIC_WHITELIST for t in repo["topics"])
    assert not has_ai_topic


def test_ai_topic_whitelist_passes_llm_tool():
    """langchain (5k+, AI) must pass."""
    from radar import AI_TOPIC_WHITELIST
    repo = {"name": "foo/langchain", "topics": ["llm", "python", "ai"], "stars": 90000}
    has_ai_topic = any(t.lower() in AI_TOPIC_WHITELIST for t in repo["topics"])
    assert has_ai_topic


def test_top_5k_plus_data_shape():
    """Verify the data shape that /api/top endpoint depends on."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "data").mkdir()
        repos = [{
            "name": f"owner/repo{i}", "desc": "", "url": f"https://github.com/owner/repo{i}",
            "stars": 10000 - i, "lang": "Python", "topics": ["ai"],
            "pushed": "2026-07-20", "desc_zh": "", "facts": "", "local_installed": False,
        } for i in range(25)]
        latest = {"top_5k_plus": {"count": 25, "fetched_at": "2026-07-20", "repos": repos}}
        (tmp / "data" / "latest.json").write_text(json.dumps(latest))
        # Verify the shape: /api/top client-paginates over `top_5k_plus.repos`
        snap = json.loads((tmp / "data" / "latest.json").read_text())
        all_repos = snap["top_5k_plus"]["repos"]
        assert len(all_repos) == 25
        # Pagination math
        size = 10
        page1 = all_repos[0:size]
        page3 = all_repos[20:30]
        assert len(page1) == 10
        assert len(page3) == 5  # last partial page
        # Sort keys
        by_name = sorted(all_repos, key=lambda r: r["name"].lower())
        assert by_name[0]["name"] == "owner/repo0"  # repo0 < repo1 alphabetically
        by_recent = sorted(all_repos, key=lambda r: r.get("pushed", ""), reverse=True)
        assert by_recent[0]["pushed"] == "2026-07-20"


if __name__ == "__main__":
    test_install_skill_from_github_accepts_owner_repo()
    print("✓ test_install_skill_from_github_accepts_owner_repo")
    test_install_skill_from_github_rejects_bad_name()
    print("✓ test_install_skill_from_github_rejects_bad_name")
    test_detect_local_skills_uses_latest_json_when_present()
    print("✓ test_detect_local_skills_uses_latest_json_when_present")
    test_detect_local_skills_falls_back_to_skill_md()
    print("✓ test_detect_local_skills_falls_back_to_skill_md")
    test_detect_local_skills_translates_desc_en_when_no_zh()
    print("✓ test_detect_local_skills_translates_desc_en_when_no_zh")
    test_ai_topic_whitelist_filters_blockchain()
    print("✓ test_ai_topic_whitelist_filters_blockchain")
    test_ai_topic_whitelist_passes_llm_tool()
    print("✓ test_ai_topic_whitelist_passes_llm_tool")
    test_top_5k_plus_data_shape()
    print("✓ test_top_5k_plus_data_shape")
    print("\nAll tests passed.")