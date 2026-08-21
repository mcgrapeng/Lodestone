"""Tests for scrapers/config_loader.py. Run: python3 -m tests.test_config"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_load_config_returns_all_sections():
    """Default config has all 10 engines + orchestrator + browser-specific blocks."""
    from scrapers.config_loader import load_config

    cfg = load_config()
    assert "orchestrator" in cfg
    assert "timeouts" in cfg
    assert "user_agents" in cfg
    # All 10 engines tracked
    engines = set(cfg["timeouts"].keys())
    assert engines == {
        "firecrawl",
        "crawl4ai",
        "playwright",
        "playwright_stealth",
        "cloudscraper",
        "httpx",
        "trafilatura",
        "beautifulsoup",
        "drissionpage",
        "agent_reach",
    }, f"missing engines: {engines}"


def test_get_timeout_returns_int():
    from scrapers.config_loader import get_timeout

    assert isinstance(get_timeout("firecrawl"), int)
    assert get_timeout("firecrawl") >= 30  # sanity


def test_get_timeout_falls_back_to_default_for_unknown_engine():
    from scrapers.config_loader import get_timeout

    assert get_timeout("nonexistent_engine_xyz", default=42) == 42
    assert get_timeout("nonexistent_engine_xyz", default=99) == 99


def test_get_priority_returns_all_engines():
    from scrapers.config_loader import get_priority

    priority = get_priority()
    assert len(priority) >= 10
    # firecrawl should be first (highest priority)
    assert priority[0] == "firecrawl"


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
