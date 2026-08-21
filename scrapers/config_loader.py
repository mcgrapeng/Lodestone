# -*- coding: utf-8 -*-
"""config.toml loader — Python 3.11+ tomllib (stdlib) / 3.10 tomli fallback.

Used by scrapers/__init__.py and each adapter to read timeouts / User-Agents /
selection strategy / engine priority without hardcoding.

If config.toml is missing, falls back to hardcoded defaults so the project
still runs out of the box. If a section/key is missing, the adapter's own
default kicks in (defense in depth).
"""

import sys
from pathlib import Path


_CONFIG_PATH = Path(__file__).parent.parent / "config.toml"


def _load_toml(path: Path) -> dict:
    if sys.version_info >= (3, 11):
        import tomllib

        with open(path, "rb") as f:
            return tomllib.load(f)
    # ponytail: Python 3.10 fallback. tomli ships a built-in module name conflict
    # so we use it as an import-only shim; tomli is BSD-licensed pure Python.
    try:
        import tomli as tomllib

        with open(path, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        return {}


# ponytail: hardcoded defaults — used when config.toml is missing or malformed.
# Matches config.toml values; keep in sync.
_DEFAULTS: dict = {
    "orchestrator": {
        "wall_clock_timeout": 60,
        "selection_strategy": "longest",
        "min_html_length": 500,
        "priority": [
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
        ],
    },
    "timeouts": {
        "firecrawl": 120,
        "crawl4ai": 120,
        "playwright": 60,
        "playwright_stealth": 60,
        "cloudscraper": 90,
        "httpx": 60,
        "trafilatura": 60,
        "beautifulsoup": 30,
        "drissionpage": 60,
        "agent_reach": 60,
    },
    "user_agents": {},
    "playwright": {"browser_args": ["--no-sandbox"], "headless": True},
    "cloudscraper": {"browser": "chrome", "platform": "linux", "desktop": True},
    "agent_reach": {"prefer_python_lib": True, "jina_format": "markdown"},
    "crawl4ai": {"llm_extraction": False},
}


def load_config() -> dict:
    """Load config.toml, falling back to _DEFAULTS on any error.

    Returns the merged config dict; each section is independent so a missing
    section doesn't break the others.
    """
    if not _CONFIG_PATH.exists():
        return _DEFAULTS
    try:
        loaded = _load_toml(_CONFIG_PATH)
    except Exception:
        return _DEFAULTS
    # ponytail: shallow merge — loaded values win over defaults; missing
    # sections fall back entirely to defaults.
    merged = {**_DEFAULTS}
    for section, values in loaded.items():
        if isinstance(values, dict) and section in merged:
            merged[section] = {**merged[section], **values}
        else:
            merged[section] = values
    return merged


def get_timeout(engine: str, default: int = 60) -> int:
    cfg = load_config()
    return cfg.get("timeouts", {}).get(engine, default)


def get_user_agent(engine: str, default: str = "") -> str:
    cfg = load_config()
    return cfg.get("user_agents", {}).get(engine, default)


def get_priority() -> list:
    cfg = load_config()
    return cfg.get("orchestrator", {}).get(
        "priority", _DEFAULTS["orchestrator"]["priority"]
    )


def get_wall_clock_timeout(default: int = 60) -> int:
    cfg = load_config()
    return cfg.get("orchestrator", {}).get("wall_clock_timeout", default)


def get_selection_strategy(default: str = "longest") -> str:
    cfg = load_config()
    return cfg.get("orchestrator", {}).get("selection_strategy", default)


def get_min_html_length(default: int = 500) -> int:
    cfg = load_config()
    return cfg.get("orchestrator", {}).get("min_html_length", default)
