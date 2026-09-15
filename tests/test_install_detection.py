"""Tests for 2026-09 installed-detection fixes. Run: python3 -m tests.test_install_detection

背景(生产 bug):已安装项目不显示「已装」。三个根因:
  A. 安装端装 opencode(~/.config/opencode/skills),检测端只扫 claude/codex
  B. installed_plugins.json 里已装但未启用的插件被 enabled 过滤整行跳过
  C. serve 匹配(_installed_segments)完全忽略 skills 目录的 origin
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest import mock  # noqa: E402

import radar  # noqa: E402


# ── _owner_repo_from_url ──────────────────────────────────────────


def test_owner_repo_from_url_normal():
    assert radar._owner_repo_from_url("https://github.com/affaan-m/ECC") == "affaan-m/ECC"


def test_owner_repo_from_url_git_suffix():
    assert (
        radar._owner_repo_from_url("https://github.com/obra/superpowers.git")
        == "obra/superpowers"
    )


def test_owner_repo_from_url_rejects_non_github():
    assert radar._owner_repo_from_url("https://gitlab.com/a/b") is None


def test_owner_repo_from_url_rejects_short_path():
    assert radar._owner_repo_from_url("https://github.com/onlyowner") is None
    assert radar._owner_repo_from_url("") is None


# ── _owner_repo_from_link_target ──────────────────────────────────


def test_link_target_resolves_owner_repo():
    tmp = Path("_t_ai_radar_test_cache").resolve()  # 绝对路径 — 安装器实际形态
    cache = tmp / "skills-cache"
    (cache / "affaan-m__ecc").mkdir(parents=True, exist_ok=True)
    link = tmp / "ecc"
    link.symlink_to(cache / "affaan-m__ecc")
    try:
        with mock.patch("radar_pkg.core.SKILLS_CACHE", cache):
            assert radar._owner_repo_from_link_target(link) == "affaan-m/ecc"
    finally:
        link.unlink(missing_ok=True)
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_link_target_ignores_foreign_targets():
    tmp = Path("_t_ai_radar_test_cache2").resolve()
    foreign = tmp / "elsewhere"
    foreign.mkdir(parents=True, exist_ok=True)
    link = tmp / "some-skill"
    link.symlink_to(foreign)
    try:
        with mock.patch("radar_pkg.core.SKILLS_CACHE", tmp / "skills-cache-not-here"):
            assert radar._owner_repo_from_link_target(link) is None
    finally:
        link.unlink(missing_ok=True)
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


# ── _installed_segments: skills origin 参与(根因 C)────────────────


def test_installed_segments_includes_skills_origin():
    local = {
        "skills": {
            "ecc": {"origin_full": "affaan-m/ecc", "url": None},
            "firecrawl": {"url": "https://github.com/firecrawl/firecrawl"},
            "no-origin": {},
        },
        "plugins": [],
    }
    segs = radar._installed_segments(local)
    assert "affaan-m/ecc" in segs
    assert "firecrawl/firecrawl" in segs
    assert not any("no-origin" in s for s in segs)


# ── _annotate_local_installed: 大小写与 seg 匹配 ───────────────────


def test_annotate_matches_case_insensitive_full_name():
    rows = {"name": "affaan-m/ECC"}
    radar._annotate_local_installed(rows, {"affaan-m/ecc"}, set())
    assert rows["local_installed"] is True


def test_annotate_matches_plugin_seg():
    # ecc 插件装了但查不到 GitHub full name — bare seg 兜底
    rows = {"name": "affaan-m/ECC"}
    radar._annotate_local_installed(rows, set(), {"ecc"})
    assert rows["local_installed"] is True


def test_annotate_no_false_positive():
    rows = {"name": "someone/other-repo"}
    radar._annotate_local_installed(rows, {"affaan-m/ecc"}, {"ecc"})
    assert rows["local_installed"] is False


# ── 平台表(根因 A)──────────────────────────────────────────────


def test_skills_root_for_all_builtin_platforms():
    assert str(radar._skills_root_for("claude")).endswith(".claude/skills")
    assert str(radar._skills_root_for("codex")).endswith(".codex/skills")
    assert "opencode" in str(radar._skills_root_for("opencode"))
    assert str(radar._skills_root_for("easycode")).endswith(".easycode/skills")


def test_skills_root_for_rejects_unknown():
    try:
        radar._skills_root_for("not-a-cli")
        raise AssertionError("should have raised")
    except ValueError:
        pass


def test_supported_clis_contains_four_platforms():
    for cli in ("claude", "codex", "opencode", "easycode"):
        assert cli in radar.SUPPORTED_CLIS


# ── detect_local_skills: 多平台扫描 + symlink origin(集成,隔离 home)──


def test_detect_scans_all_platform_dirs_and_recovers_origin():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        cache = home / "cache" / "skills"
        (cache / "affaan-m__ecc").mkdir(parents=True)
        platforms = {
            "claude": str(home / "claude" / "skills"),
            "codex": str(home / "codex" / "skills"),
            "opencode": str(home / "opencode" / "skills"),
            "easycode": str(home / "easycode" / "skills"),
        }
        for cli, p in platforms.items():
            d = Path(p)
            d.mkdir(parents=True)
            if cli == "opencode":
                # 本工具安装的真实形态:symlink → SKILLS_CACHE/owner__repo
                (d / "ecc").symlink_to(cache / "affaan-m__ecc")
            else:
                (d / "handmade").mkdir()  # 手装技能,无任何 origin

        with mock.patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", platforms), mock.patch(
            "radar_pkg.core.SKILLS_CACHE", cache
        ), mock.patch("radar_pkg.detect._load_repo_index", return_value={}), mock.patch(
            "radar_pkg.core.SKILL_ORIGINS", home / "nope" / "origins.json"
        ):
            local = radar.detect_local_skills(force=True)

        skills = local["skills"]
        assert "ecc" in skills and "handmade" in skills
        assert skills["ecc"]["opencode"] is True
        assert skills["handmade"]["claude"] is True
        assert skills["handmade"]["opencode"] is False
        # symlink 目标还原 origin(根因 C 的数据来源)
        assert skills["ecc"].get("origin_full") == "affaan-m/ecc"
        # 还原出的 full name 进入匹配集合(卡片已装的最终判据)
        segs = radar._installed_segments(local)
        assert "affaan-m/ecc" in segs


def test_detect_keeps_disabled_plugin_as_installed():
    """根因 B:installed_plugins.json 是安装记录;未启用 ≠ 未安装。
    detect_local_skills 深度绑定真实 HOME(Path.home() 遍布模块),单测不便整体
    重定向;此处以同构 fake local 验证下游匹配链不再丢弃未启用插件。"""
    fake_local = {
        "skills": {},
        "commands": {},
        "agents": {},
        "plugins": [
            {
                "name": "ecc",
                "marketplace": "ecc",
                "version": "2.0.0",
                "url": None,
                "enabled": False,
            }
        ],
    }
    segs = radar._build_plugin_segs(fake_local)
    assert "ecc" in segs, "未启用插件必须仍参与已装匹配"


# ── uninstall 闭环(2026-09 闭环验证暴露的两个真 bug)──────────────────


def test_uninstall_accepts_owner_repo_form():
    """U1:install 要求 owner/repo,uninstall 的字符集校验却不含 '/',直接调 API
    卸 'octocat/Hello-World' 会 400(前端碰巧传裸段才没炸)— 两种形式都必须接受。"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        platforms = {"claude": str(home / "claude" / "skills")}
        for p in platforms.values():
            Path(p).mkdir(parents=True, exist_ok=True)
        (Path(platforms["claude"]) / "Hello-World").symlink_to(home)  # 任意目标
        with mock.patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", platforms), mock.patch.object(
            radar, "SKILL_ORIGINS", home / "nope" / "origins.json"
        ), mock.patch("radar_pkg.core.SKILLS_CACHE", home / "nope"):
            result = radar.uninstall_skill("octocat/Hello-World")  # 修复前:ValueError
        assert not (Path(platforms["claude"]) / "Hello-World").exists()
        assert result["removed_links"]


def test_uninstall_cleans_all_platforms():
    """U2:uninstall 硬编码只清 claude/codex — opencode/easycode 链接残留会让
    卸载后「已装」徽标不消失。必须遍历平台表全平台。"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        platforms = {
            "claude": str(home / "claude" / "skills"),
            "codex": str(home / "codex" / "skills"),
            "opencode": str(home / "opencode" / "skills"),
            "easycode": str(home / "easycode" / "skills"),
        }
        for p in platforms.values():
            d = Path(p)
            d.mkdir(parents=True, exist_ok=True)
            (d / "Hello-World").symlink_to(home)
        with mock.patch("radar_pkg.detect._SKILL_PLATFORM_PATHS", platforms), mock.patch.object(
            radar, "SKILL_ORIGINS", home / "nope" / "origins.json"
        ), mock.patch("radar_pkg.core.SKILLS_CACHE", home / "nope"):
            radar.uninstall_skill("Hello-World")
        for cli, p in platforms.items():
            assert not (Path(p) / "Hello-World").exists(), f"{cli} 链接未清理"


if __name__ == "__main__":
    import inspect

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
