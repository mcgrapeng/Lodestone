"""Tests for scrapers/config_loader.py. Run: python3 -m tests.test_config"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_load_config_returns_all_sections():
    """timeouts/user_agents 仍为全部 14 个适配器保留配置（停用的可随时重启）。"""
    from scrapers.config_loader import load_config

    cfg = load_config()
    assert "orchestrator" in cfg
    assert "timeouts" in cfg
    assert "user_agents" in cfg
    # 超时/UA 配置覆盖所有适配器（含 2026-09 停用的 10 个 — 重新启用无需补配置）
    engines = set(cfg["timeouts"].keys())
    assert engines == {
        "httpx", "cloudscraper", "playwright_stealth", "jina",
        "firecrawl", "crawl4ai", "playwright", "nodriver",
        "crawlee", "scrapy", "agent_reach", "trafilatura",
        "beautifulsoup", "drissionpage",
    }, f"missing engines: {engines}"


def test_get_timeout_returns_int():
    from scrapers.config_loader import get_timeout

    assert isinstance(get_timeout("firecrawl"), int)
    assert get_timeout("firecrawl") >= 30  # sanity


def test_get_timeout_falls_back_to_default_for_unknown_engine():
    from scrapers.config_loader import get_timeout

    assert get_timeout("nonexistent_engine_xyz", default=42) == 42
    assert get_timeout("nonexistent_engine_xyz", default=99) == 99


def test_get_priority_returns_curated_engines():
    """2026-09：priority 白名单收敛为 4 个精选引擎，轻→重排序（httpx 打头）。"""
    from scrapers.config_loader import get_priority

    priority = get_priority()
    assert priority == ["httpx", "cloudscraper", "playwright_stealth", "jina"]


def test_selection_strategy_defaults_to_tiered():
    """默认编排 = tiered（分级 fallback + 质量门）。"""
    from scrapers.config_loader import get_selection_strategy

    assert get_selection_strategy() == "tiered"


def test_get_user_agent_returns_string():
    from scrapers.config_loader import get_user_agent

    ua = get_user_agent("playwright", default="fallback-ua")
    assert isinstance(ua, str)
    assert len(ua) > 0


def test_load_config_handles_missing_file():
    """If config.toml is missing, returns defaults without crashing."""

    from scrapers import config_loader

    # ponytail: monkey-patch _CONFIG_PATH to a non-existent path
    original = config_loader._CONFIG_PATH
    config_loader._CONFIG_PATH = Path("/tmp/nonexistent_xyz_999.toml")
    try:
        cfg = config_loader.load_config()
        assert "orchestrator" in cfg
        assert "timeouts" in cfg
    finally:
        config_loader._CONFIG_PATH = original


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
