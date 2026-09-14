"""Tests for radar_pkg.settings. Run: python3 -m tests.test_settings
Uses a tmp dir for SETTINGS_PATH so it doesn't touch real data/settings.json."""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from radar_pkg import core, settings


def _use_tmp(monkeypatch_tmpdir: str) -> None:
    """Swap core.SETTINGS_PATH to a tmp file for test isolation."""
    core.SETTINGS_PATH = Path(monkeypatch_tmpdir) / "settings.json"


def test_save_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp(tmp)
        d = {"provider": "openai", "openai": {"api_key": "sk-test", "model": "gpt-4o-mini"}}
        settings.save(d)
        loaded = settings.load()
        assert loaded["provider"] == "openai"
        assert loaded["openai"]["api_key"] == "sk-test"
        assert "updated_at" in loaded


def test_load_missing_file_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp(tmp)
        assert settings.load() is None


def test_load_corrupt_file_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp(tmp)
        core.SETTINGS_PATH.write_text("{not valid json")
        assert settings.load() is None


def test_save_atomic_no_tmp_residue():
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp(tmp)
        settings.save({"provider": "openai"})
        assert core.SETTINGS_PATH.exists()
        assert not Path(str(core.SETTINGS_PATH) + ".tmp").exists()


def test_save_filters_unknown_keys():
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp(tmp)
        settings.save({"provider": "openai", "evil": "x", "__import__": "os"})
        loaded = settings.load()
        assert "evil" not in loaded
        assert "__import__" not in loaded


def test_active_config_falls_back_to_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp(tmp)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-test")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        provider, fields = settings.active_config()
        assert provider == "anthropic"
        assert fields["api_key"] == "sk-env-test"
        assert fields["model"]  # default model set


def test_active_config_picks_settings_over_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp(tmp)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
        settings.save({"provider": "anthropic", "anthropic": {"api_key": "sk-file", "model": "claude-3-5-haiku-latest"}})
        provider, fields = settings.active_config()
        assert provider == "anthropic"
        assert fields["api_key"] == "sk-file"


if __name__ == "__main__":
    # ponytail: tests use monkeypatch from pytest but we don't have pytest. Use
    # monkeypatch.setenv via os.environ + monkeypatch.delenv via os.unsetenv
    # wrapper. Override before running:
    class _M:
        @staticmethod
        def setenv(k, v):
            os.environ[k] = v
        @staticmethod
        def delenv(k, raising=True):
            os.environ.pop(k, None)
    import builtins
    builtins.monkeypatch = _M
    import inspect
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        # ponytail: pass _M (class with staticmethods) when test signature expects monkeypatch,
        # so the verbatim pytest-style test functions work without pytest.
        if "monkeypatch" in inspect.signature(fn).parameters:
            fn(_M)
        else:
            fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")