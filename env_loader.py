# -*- coding: utf-8 -*-
"""Tiny .env loader — no python-dotenv dependency.

Loads KEY=VALUE lines from the project .env into os.environ WITHOUT overriding
variables that are already set in the shell (shell wins, like docker --env-file).

Why: gh CLI honors GH_TOKEN/GITHUB_TOKEN from the environment, which is a
non-interactive alternative to `gh auth login` (the stored token can expire —
see 2026-09 incident). Also feeds JINA_API_KEY / FIRECRAWL_API_KEY to the
scraper adapters. Secrets never go into config.toml (it's committed).
"""
from __future__ import annotations

import os
from pathlib import Path

_ENV_PATH = Path(__file__).parent / ".env"


def load_env(quiet: bool = True) -> list[str]:
    """Export .env into os.environ. Returns the list of keys loaded (not
    necessarily new — a key already present in the shell keeps its shell value)."""
    if not _ENV_PATH.exists():
        return []
    loaded: list[str] = []
    try:
        for line in _ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if not key:
                continue
            loaded.append(key)
            os.environ.setdefault(key, value)  # shell env wins over .env
    except Exception as e:
        if not quiet:
            print(f"  [warn] .env load failed: {e}", file=__import__("sys").stderr)
    return loaded
