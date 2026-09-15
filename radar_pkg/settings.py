"""LLM settings persistence — data/settings.json (gitignored).

source of truth for radar_pkg.llm_analyze during crawl. Env vars are fallback
for users who don't use the UI. Atomic writes via .tmp + rename.

Ponytail: keep file <100 lines. All public functions take/return plain dicts.
This module must not import llm_analyze (would cause circular import).
"""
from __future__ import annotations

import json
import os
import sys
import time

from radar_pkg import core


_KEYS = {"provider", "anthropic", "openai", "ollama", "min_stars", "updated_at"}

_VALID_PROVIDERS = {"anthropic", "openai", "ollama"}


def load() -> dict | None:
    """Read settings file. Returns None if missing or corrupt (env fallback wins)."""
    if not core.SETTINGS_PATH.exists():
        return None
    try:
        return json.loads(core.SETTINGS_PATH.read_text())
    except (OSError, ValueError) as e:
        # ponytail: corrupt file should not crash serve. Log once, fall back to env.
        print(f"[settings] corrupt file, falling back to env: {e}", file=sys.stderr)
        return None


def save(d: dict) -> None:
    """Atomic write — only whitelisted keys reach disk."""
    payload = {k: v for k, v in d.items() if k in _KEYS}
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    core.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = core.SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    tmp.replace(core.SETTINGS_PATH)


def _detect_env_provider() -> str | None:
    """Env-only provider detection. Skips Ollama probe (saves 2s timeout)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("OLLAMA_HOST"):
        return "ollama"
    return None


def _env_fields_for(provider: str) -> dict:
    if provider == "anthropic":
        return {
            "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        }
    if provider == "openai":
        return {
            "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        }
    if provider == "ollama":
        return {
            "host": os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
            "model": os.environ.get("OLLAMA_MODEL", "llama3.1"),
        }
    return {}


def active_config() -> tuple[str, dict]:
    """Return (provider_name, fields_dict). Settings file wins; env is fallback.

    Settings file takes precedence when present + has fields for the chosen provider.
    If file has provider but missing fields, env fills them in.
    """
    s = load() or {}
    provider = s.get("provider") if s else None
    if not provider or provider not in _VALID_PROVIDERS:
        provider = _detect_env_provider() or "openai"
    saved_fields = (s.get(provider) if s else None) or {}
    if not saved_fields:
        fields = _env_fields_for(provider)
    else:
        # Merge: env provides defaults for any sub-key missing in saved fields
        env_fields = _env_fields_for(provider)
        fields = {**env_fields, **saved_fields}
    return provider, fields