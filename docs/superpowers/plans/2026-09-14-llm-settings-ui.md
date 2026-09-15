# LLM Settings UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a settings UI (gear icon → right drawer) that lets the user configure the LLM provider, endpoint, API key, and model used by `radar_pkg/llm_analyze` during crawl-time project-intro generation. Settings persist to `data/settings.json` (gitignored) so crawl subprocess reads them on the next run.

**Architecture:** Three layers — (1) `radar_pkg/settings.py` loads/saves/queries disk JSON with env-var fallback; (2) `radar_pkg/llm_analyze.py` reads from settings before env; (3) new HTTP endpoints (`GET/POST /api/settings`, `POST /api/llm/test`) + React `SettingsDrawer` for the UI. Atomic file writes via `.tmp + rename`. Settings file is the source of truth; env vars remain a fallback for users who don't use the UI.

**Tech Stack:** Python 3.10+ stdlib only (no new deps). React 19 + Vite 6 + Tailwind v4 frontend (no new deps). Tests: stdlib `if __name__ == "__main__":` pattern matching existing `tests/*.py`.

## Global Constraints

- **Python:** 3.10+. Stdlib only. No new pip dependencies.
- **Frontend:** React 19 + Vite 6 + Tailwind v4 + lucide-react + Appica UI (existing).
- **Tests:** Stdlib test runner pattern (see `tests/test_db.py:336-347`). No pytest.
- **File write pattern:** Always `.tmp + rename` for atomicity (see `radar_pkg/translate.py:999-1007`).
- **Threading:** Use existing `_TRANSLATE_LOCK` style if needed; settings writes are simple JSON and unlikely to race.
- **Origin check:** All new POST endpoints MUST call `self._origin_forbidden()` first (matches existing endpoints in `radar_pkg/serve.py:885-887`).
- **Concurrency model:** Crawl is a separate subprocess spawned by serve (`Popen`). It inherits file access; settings file changes are visible immediately to the next crawl without restart.
- **Pre-existing debt (do NOT fix in this plan):** `__pycache__/` files tracked in git, missing `.gitignore`. Out of scope; tracked separately.
- **5-bucket schema (DO NOT change):** `what / can_do / problem / alternatives (with pros+cons) / when_to_use`. Defined in `radar_pkg/llm_analyze.py:130-140` prompt + `_normalize()`.
- **Existing constants to reuse:** `core.DATA` (settings path), `core.SKILLS_CACHE` style naming.
- **No new dependencies** in any `requirements.txt` or `frontend/package.json`.

## File Structure

| Path | Action | Responsibility |
|------|--------|----------------|
| `radar_pkg/core.py` | modify | Add `SETTINGS_PATH = DATA / "settings.json"` constant |
| `radar_pkg/settings.py` | **create** | Settings persistence + env fallback (`load/save/active_config`) |
| `radar_pkg/llm_analyze.py` | modify | Read from `settings.active_config()` instead of `os.environ` directly |
| `radar_pkg/serve.py` | modify | Add `GET/POST /api/settings` + `POST /api/llm/test` endpoints |
| `.gitignore` | **create** | Ignore `data/settings.json` + `data/.settings.json.tmp` |
| `tests/test_settings.py` | **create** | Stdlib tests for settings module |
| `tests/test_serve_settings.py` | **create** | Stdlib tests for HTTP endpoints |
| `frontend/src/lib/types.ts` | modify | Add `Settings` type |
| `frontend/src/lib/api.ts` | modify | Add `getSettings / saveSettings / testLlm` methods |
| `frontend/src/components/SettingsDrawer.tsx` | **create** | Right-side drawer component |
| `frontend/src/components/Header.tsx` | modify | Add gear icon button + status dot |
| `frontend/src/App.tsx` | modify | Mount drawer + state management |

---

### Task 1: Foundation — SETTINGS_PATH + .gitignore

**Files:**
- Modify: `radar_pkg/core.py:35-46` (add constant near other path constants)
- Create: `.gitignore` (new file at project root)

**Interfaces:**
- Consumes: nothing (foundation)
- Produces: `core.SETTINGS_PATH: Path` — `DATA / "settings.json"`, used by Task 2

- [ ] **Step 1: Add SETTINGS_PATH constant to core.py**

Read `radar_pkg/core.py:35-46` to confirm the exact existing block. After line 41 (`SKILL_PROBE_CACHE = DATA / "skill_probe_cache.json"`), add the new constant.

Edit:
```python
# ponytail: 2026-09 — LLM settings UI 持久化（gitignore 中）。crawl 读这文件获取
# provider + endpoint + key + model。
SETTINGS_PATH = DATA / "settings.json"
```

- [ ] **Step 2: Verify import works**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -c "from radar_pkg import core; print(core.SETTINGS_PATH)"`
Expected: prints something like `/Users/.../lodestone/data/settings.json`

- [ ] **Step 3: Create .gitignore at project root**

Write file `.gitignore`:
```
# ponytail: 2026-09 — LLM settings UI 持久化 (含明文 API key, 不入 git)
data/settings.json
data/.settings.json.tmp

# ponytail: 以下条目是历史遗留的 pre-existing debt, 本次不改。_pycache__ 早被
# 误入 git,清理需 git rm -r --cached,留待后续统一整理。
__pycache__/
*.pyc
.venv/
frontend/node_modules/
frontend/dist/
data/serve.log
data/restart.log
data/crawl.lock
data/crawl.lock.stale-*
data/serve.log.*
graphify-out/
.idea/
.serena/
```

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone
git add radar_pkg/core.py .gitignore
git commit -m "feat(settings): add SETTINGS_PATH constant + .gitignore for data/settings.json

SETTINGS_PATH = DATA / 'settings.json' — written by new radar_pkg.settings
module, read by radar_pkg.llm_analyze during crawl-time LLM analysis.
.gitignore covers it (API key plaintext) plus pre-existing debt items
(pycache tracked, venv, etc.) for future cleanup."
```

---

### Task 2: settings.py module + tests

**Files:**
- Create: `radar_pkg/settings.py`
- Create: `tests/test_settings.py`

**Interfaces:**
- Consumes: `core.SETTINGS_PATH` (from Task 1)
- Produces:
  - `load() -> dict | None` — read file, return parsed dict or None if missing/corrupt
  - `save(d: dict) -> None` — atomic write via `.tmp + rename`, only whitelisted keys
  - `active_config() -> tuple[str, dict]` — (provider_name, fields_dict), settings-first env-fallback

- [ ] **Step 1: Write the failing tests**

Create `tests/test_settings.py`:
```python
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
    import pytest  # noqa: F401
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
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_settings 2>&1 | tail -5`
Expected: `ModuleNotFoundError: No module named 'radar_pkg.settings'`

- [ ] **Step 3: Implement settings.py**

Create `radar_pkg/settings.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_settings 2>&1 | tail -10`
Expected: All tests pass (`✓ test_xxx` lines followed by `All tests passed.`)

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone
git add radar_pkg/settings.py tests/test_settings.py
git commit -m "feat(settings): radar_pkg.settings module with disk persistence

load() reads data/settings.json (gitignored) or returns None.
save() writes atomically via .tmp + rename, only whitelisted keys reach disk.
active_config() resolves (provider, fields) tuple with settings file winning
over env fallback — env fills missing sub-keys when file is partial.

Used by radar_pkg.llm_analyze (next task) and serve.py /api/settings
endpoints (Tasks 4-5). No new dependencies. 7 stdlib tests cover
roundtrip / corrupt / atomic / unknown-key filtering / env fallback."
```

---

### Task 3: llm_analyze.py reads from settings

**Files:**
- Modify: `radar_pkg/llm_analyze.py:60-72` (constants), `:92-107` (detect_provider), `:209-263` (call_* funcs), `:72` (min_stars)

**Interfaces:**
- Consumes: `settings.active_config() -> (provider, fields_dict)` (from Task 2)
- Produces: Same external API (`analyze_one`, `analyze_many`, `detect_provider`) — internal reads change
- All existing tests must continue to pass (test_radar, test_translate)

- [ ] **Step 1: Replace env-var constants with settings.active_config() lookup**

Read `radar_pkg/llm_analyze.py:60-72`. Currently the constants `_ANTHROPIC_MODEL`, `_OPENAI_DEFAULT_BASE`, `_OPENAI_MODEL`, `_OLLAMA_HOST`, `_OLLAMA_MODEL`, `_MIN_STARS_FOR_ANALYSIS` are module-level frozen reads of `os.environ`. Replace with lazy lookup.

Strategy: keep the existing env-var defaults as fallback. Add a helper `_config()` that returns `(provider, fields)` from settings. The call_* functions look up `_config()` at call time (not at import time) so settings changes take effect without reimport.

Replace the entire block (lines 60-72) with:
```python
from radar_pkg import settings as _settings


def _config() -> tuple[str, dict]:
    """Lazy lookup of active LLM config. Settings file wins; env is fallback."""
    return _settings.active_config()


def _min_stars() -> int:
    """Min stars threshold — settings.min_stars > env LLM_MIN_STARS > default 50."""
    s = _settings.load() or {}
    v = s.get("min_stars")
    if v is not None:
        try:
            return int(v)
        except (TypeError, ValueError):
            pass
    try:
        return int(os.environ.get("LLM_MIN_STARS", "50"))
    except ValueError:
        return 50
```

- [ ] **Step 2: Replace detect_provider() to consult settings first**

Read `radar_pkg/llm_analyze.py:92-107`. Replace:
```python
def detect_provider() -> str | None:
    """Return active provider name ('anthropic' / 'openai' / 'ollama' / None).
    Settings file is source of truth; env is fallback for users without the UI."""
    s = _settings.load() or {}
    chosen = s.get("provider")
    if chosen in _settings._VALID_PROVIDERS:
        # Settings has a valid provider selected — check it has minimum required fields
        fields = s.get(chosen) or {}
        if chosen == "anthropic" and fields.get("api_key"):
            return "anthropic"
        if chosen == "openai" and fields.get("api_key") and fields.get("base_url"):
            return "openai"
        if chosen == "ollama" and fields.get("host"):
            return "ollama"
        # Settings present but incomplete — fall through to env
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return "ollama"
    except Exception:
        pass
    return None
```

- [ ] **Step 3: Update _call_anthropic to use settings**

Read `radar_pkg/llm_analyze.py:209-229`. Replace the `_call_anthropic` function:
```python
def _call_anthropic(prompt: str, *, max_tokens: int = 800) -> str:
    """Claude Messages API. Reads api_key + model from settings."""
    _, fields = _config()
    api_key = fields.get("api_key", "")
    if not api_key:
        raise RuntimeError("anthropic api_key not configured")
    model = fields.get("model", "claude-3-5-haiku-latest")
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    resp = _post_json(
        _ANTHROPIC_URL,
        payload,
        {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        },
    )
    parts = resp.get("content") or []
    texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
    return "\n".join(texts)
```

- [ ] **Step 4: Update _call_openai to use settings**

Read `radar_pkg/llm_analyze.py:232-249`. Replace:
```python
def _call_openai(prompt: str, *, max_tokens: int = 800) -> str:
    """OpenAI Chat Completions API (custom base_url). Reads from settings."""
    _, fields = _config()
    api_key = fields.get("api_key", "")
    if not api_key:
        raise RuntimeError("openai api_key not configured")
    base = fields.get("base_url", "https://api.openai.com/v1").rstrip("/")
    model = fields.get("model", "gpt-4o-mini")
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    resp = _post_json(
        f"{base}/v1/chat/completions",
        payload,
        {"Authorization": f"Bearer {api_key}"},
    )
    choices = resp.get("choices") or []
    return (choices[0].get("message") or {}).get("content", "")
```

- [ ] **Step 5: Update _call_ollama to use settings**

Read `radar_pkg/llm_analyze.py:252-263`. Replace:
```python
def _call_ollama(prompt: str, *, max_tokens: int = 800) -> str:
    """Ollama /api/chat. Reads host + model from settings."""
    _, fields = _config()
    host = fields.get("host", "http://127.0.0.1:11434").rstrip("/")
    model = fields.get("model", "llama3.1")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": max_tokens},
        "format": "json",
    }
    resp = _post_json(f"{host}/api/chat", payload, {})
    return (resp.get("message") or {}).get("content", "")
```

- [ ] **Step 6: Update analyze_many and _dispatch to use _min_stars()**

Read `radar_pkg/llm_analyze.py:335-393` (analyze_many). Replace the threshold check:
```python
    threshold = _min_stars()
    for r in repos:
        name = r.get("name") or ""
        if "/" not in name:
            continue
        if (r.get("stars") or 0) < threshold:
            continue
        if not (r.get("readme") or ""):
            continue
        todo.append(r)
```

Also update the print line at `radar_pkg/llm_analyze.py:358`:
```python
            f"  · llm analysis: no eligible repos (need stars≥{threshold} + README)"
```

- [ ] **Step 7: Verify existing tests still pass**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_radar 2>&1 | tail -3`
Expected: `All tests passed.`

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_translate 2>&1 | tail -3`
Expected: `All 16 tests passed.`

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_settings 2>&1 | tail -3`
Expected: `All tests passed.`

- [ ] **Step 8: Commit**

```bash
cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone
git add radar_pkg/llm_analyze.py
git commit -m "feat(llm_analyze): read provider config from settings (env fallback)

detect_provider now consults data/settings.json first; env vars are fallback
for users who don't use the UI. _call_anthropic / _call_openai / _call_ollama
pull api_key / base_url / host / model from settings.active_config() at call
time (not import time) so settings changes take effect on next crawl without
reimport.

min_stars threshold reads settings.min_stars > env LLM_MIN_STARS > default 50.

Existing tests (test_radar / test_translate) continue to pass — they exercise
the env fallback path."
```

---

### Task 4: /api/settings HTTP endpoints

**Files:**
- Modify: `radar_pkg/serve.py` — add `GET /api/settings` handler in `do_GET`, add `POST /api/settings` handler in `do_POST`
- Create: `tests/test_serve_settings.py`

**Interfaces:**
- Consumes: `settings.load()`, `settings.save(d)` (from Task 2)
- Produces:
  - `GET /api/settings` → `200 {"settings": <dict|null>, "defaults": <dict>, "saved_at": <str|null>}`
  - `POST /api/settings` → `200 {"ok": true}` on save, `400 {"ok": false, "error": "..."}` on validation

- [ ] **Step 1: Write the failing test**

Create `tests/test_serve_settings.py`:
```python
"""Tests for /api/settings HTTP endpoints. Spawns radar.py serve as subprocess.
Run: python3 -m tests.test_serve_settings"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from radar_pkg import core


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _post_json(url: str, body: dict, timeout: float = 5) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _get(url: str, timeout: float = 5) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _spawn_serve(tmp_settings: Path) -> tuple[subprocess.Popen, int]:
    """Spawn radar.py serve on a free port. Remap SETTINGS_PATH to tmp."""
    port = _free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)
    # Override SETTINGS_PATH to a tmp file via env-driven test hook
    # (settings.py uses core.SETTINGS_PATH, not env; we monkeypatch at runtime below)
    p = subprocess.Popen(
        [sys.executable, "radar.py", "serve", str(port)],
        cwd=str(Path(__file__).parent.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Wait for port to bind (up to 5s)
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return p, port
        except OSError:
            time.sleep(0.1)
    p.terminate()
    raise RuntimeError(f"serve did not bind {port} in 5s")


def _override_settings_path(p: subprocess.Popen, path: Path) -> None:
    """Patch core.SETTINGS_PATH inside the spawned process. Not feasible cross-process;
    tests below use the real data/settings.json with cleanup."""
    # NOTE: cross-process monkeypatch is hard. Instead, tests use the real
    # data/settings.json (the gitignored one) and back it up if it exists.
    pass


def _stop(p: subprocess.Popen) -> None:
    try:
        p.terminate()
        p.wait(timeout=3)
    except Exception:
        p.kill()


def _real_settings_backup() -> tuple[Path | None, bytes | None]:
    p = Path("data/settings.json")
    if p.exists():
        return p, p.read_bytes()
    return None, None


def _real_settings_restore(backup: tuple[Path | None, bytes | None]) -> None:
    p, data = backup
    if p is None:
        Path("data/settings.json").unlink(missing_ok=True)
    else:
        Path("data/settings.json").write_bytes(data)


# Tests run sequentially against real serve subprocess on a free port

def test_get_settings_returns_null_when_no_file():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        # Wait for serve to be fully ready (handler thread up)
        time.sleep(0.5)
        status, body = _get(f"http://127.0.0.1:{port}/api/settings")
        assert status == 200
        assert body.get("settings") is None or body.get("settings") == {}
    finally:
        _stop(p)
        _real_settings_restore(backup)


def test_post_then_get_roundtrips():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        time.sleep(0.5)
        body = {
            "provider": "openai",
            "openai": {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o-mini"},
        }
        status, resp = _post_json(f"http://127.0.0.1:{port}/api/settings", body)
        assert status == 200, f"POST failed: {resp}"
        assert resp.get("ok") is True
        status, resp = _get(f"http://127.0.0.1:{port}/api/settings")
        assert status == 200
        assert resp["settings"]["provider"] == "openai"
        assert resp["settings"]["openai"]["api_key"] == "sk-test"
    finally:
        _stop(p)
        _real_settings_restore(backup)


def test_post_rejects_unknown_field():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        time.sleep(0.5)
        body = {"provider": "openai", "evil_key": "rm -rf /"}
        status, resp = _post_json(f"http://127.0.0.1:{port}/api/settings", body)
        assert status == 400, f"expected 400 got {status}"
        assert "ok" in resp and resp["ok"] is False
    finally:
        _stop(p)
        _real_settings_restore(backup)


def test_post_validates_provider():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        time.sleep(0.5)
        body = {"provider": "unknown_provider"}
        status, resp = _post_json(f"http://127.0.0.1:{port}/api/settings", body)
        assert status == 400
    finally:
        _stop(p)
        _real_settings_restore(backup)


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_serve_settings 2>&1 | tail -5`
Expected: `urllib.error.HTTPError: HTTP Error 404` (endpoint doesn't exist yet)

- [ ] **Step 3: Add GET /api/settings to serve.py**

Read `radar_pkg/serve.py:280-310` (somewhere in `do_GET`) to find a good insertion point. Add a new branch:
```python
            if self.path == "/api/settings":
                # ponytail: settings UI 持久化层。无文件返 null + 默认 schema。
                from radar_pkg import settings as _settings
                loaded = _settings.load()
                self._json({
                    "settings": loaded,
                    "updated_at": (loaded or {}).get("updated_at"),
                })
                return
```

Insert this AFTER the existing `/api/health` block and BEFORE `/api/data`. The exact line depends on the existing order — use the same pattern as the existing branch blocks.

- [ ] **Step 4: Add POST /api/settings to serve.py**

Read `radar_pkg/serve.py:885-925` (the do_POST origin check + /api/restart handler) for context. Add a new branch AFTER the origin check:
```python
            if self.path == "/api/settings":
                # ponytail: 保存 LLM 设置。仅白名单字段落盘（防注入），
                # provider 必须在 3 个允许值内。
                try:
                    body = self._read_body()
                    from radar_pkg import settings as _settings
                    provider = body.get("provider", "")
                    if provider not in _settings._VALID_PROVIDERS:
                        self._json({"ok": False, "error": f"provider must be one of {sorted(_settings._VALID_PROVIDERS)}"}, status=400)
                        return
                    _settings.save(body)
                    self._json({"ok": True})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=500)
                return
```

Note: `_settings.save` already filters unknown keys via the `_KEYS` whitelist.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_serve_settings 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 6: Smoke-test endpoint manually**

Verify the endpoint is wired by hitting the running serve from earlier:
```bash
rtk curl --noproxy '*' -s -X POST http://127.0.0.1:8765/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"provider":"openai","openai":{"api_key":"sk-test","model":"gpt-4o-mini","base_url":"https://api.openai.com/v1"}}'
```
Expected: `{"ok": true}`

Then:
```bash
rtk curl --noproxy '*' -s http://127.0.0.1:8765/api/settings
```
Expected: JSON with the saved settings + updated_at.

Then revert (delete the test file):
```bash
rtk rm data/settings.json
```

- [ ] **Step 7: Commit**

```bash
cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone
git add radar_pkg/serve.py tests/test_serve_settings.py
git commit -m "feat(serve): GET/POST /api/settings endpoints

GET returns current settings file or null + updated_at. POST validates
provider is in {anthropic, openai, ollama}, then calls settings.save
which already whitelists persisted keys (defense-in-depth against
field injection). Both endpoints use the existing _origin_forbidden()
guard and _json() helpers.

4 stdlib tests: missing file returns null, roundtrip persists, unknown
field is rejected at save, invalid provider returns 400."
```

---

### Task 5: POST /api/llm/test endpoint

**Files:**
- Modify: `radar_pkg/serve.py` — add new branch in `do_POST` for `/api/llm/test`
- Modify: `tests/test_serve_settings.py` — add `test_llm_test_with_invalid_key` (rename file later if needed)

**Interfaces:**
- Consumes: `settings._VALID_PROVIDERS`, `settings._env_fields_for(provider)`, `urllib.request` for upstream call
- Produces: `POST /api/llm/test {provider, ...fields}` → `200 {ok: true, model: "..."}` or `200 {ok: false, error: "..."}` (always 200 — failures are domain-level, not transport-level)

- [ ] **Step 1: Add the failing test**

Append to `tests/test_serve_settings.py`:
```python
def test_llm_test_with_invalid_key_returns_error_not_500():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        time.sleep(0.5)
        # Anthropic with a fake key — should return {ok: false, error} not 500
        body = {
            "provider": "anthropic",
            "anthropic": {"api_key": "sk-ant-fake-for-test", "model": "claude-3-5-haiku-latest"},
        }
        status, resp = _post_json(f"http://127.0.0.1:{port}/api/llm/test", body)
        # Upstream call to Anthropic will fail (DNS OK but auth fails) — but the
        # endpoint should catch and return {ok: false, error: "..."} with 200.
        assert status == 200, f"expected 200 even on upstream fail, got {status}: {resp}"
        assert resp.get("ok") is False
        assert "error" in resp
    finally:
        _stop(p)
        _real_settings_restore(backup)


def test_llm_test_rejects_unknown_provider():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        time.sleep(0.5)
        body = {"provider": "bogus", "bogus": {}}
        status, resp = _post_json(f"http://127.0.0.1:{port}/api/llm/test", body)
        assert status == 400
    finally:
        _stop(p)
        _real_settings_restore(backup)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_serve_settings 2>&1 | tail -5`
Expected: HTTP 404 (endpoint doesn't exist).

- [ ] **Step 3: Implement POST /api/llm/test**

Add to `radar_pkg/serve.py` `do_POST` AFTER the `/api/settings` branch:
```python
            if self.path == "/api/llm/test":
                # ponytail: 用前端提供的 provider + fields 临时测一次。
                # 不持久化，只为「连通性 + 模型存在」反馈。
                # SSRF note: 接受任意 URL, threat model 是 loopback-only serve。
                try:
                    body = self._read_body()
                    from radar_pkg import settings as _settings
                    provider = body.get("provider", "")
                    if provider not in _settings._VALID_PROVIDERS:
                        self._json({"ok": False, "error": f"provider must be one of {sorted(_settings._VALID_PROVIDERS)}"}, status=400)
                        return
                    fields = body.get(provider, {})
                    # Build minimal test request per provider
                    if provider == "anthropic":
                        if not fields.get("api_key"):
                            self._json({"ok": False, "error": "anthropic.api_key required"}); return
                        payload = {"model": fields.get("model", "claude-3-5-haiku-latest"), "max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]}
                        req = urllib.request.Request(
                            "https://api.anthropic.com/v1/messages",
                            data=json.dumps(payload).encode(),
                            headers={"x-api-key": fields["api_key"], "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                            method="POST",
                        )
                    elif provider == "openai":
                        if not fields.get("api_key"):
                            self._json({"ok": False, "error": "openai.api_key required"}); return
                        base = (fields.get("base_url") or "https://api.openai.com/v1").rstrip("/")
                        payload = {"model": fields.get("model", "gpt-4o-mini"), "max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]}
                        req = urllib.request.Request(
                            f"{base}/v1/chat/completions",
                            data=json.dumps(payload).encode(),
                            headers={"Authorization": f"Bearer {fields['api_key']}", "Content-Type": "application/json"},
                            method="POST",
                        )
                    else:  # ollama
                        host = (fields.get("host") or "http://127.0.0.1:11434").rstrip("/")
                        req = urllib.request.Request(f"{host}/api/tags", method="GET")
                    try:
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            if resp.status >= 400:
                                self._json({"ok": False, "error": f"upstream {resp.status}"})
                                return
                            body_text = resp.read()
                            # Try to extract model from response (best-effort)
                            model = fields.get("model", "")
                            try:
                                parsed = json.loads(body_text)
                                if provider == "openai":
                                    model = (parsed.get("model") or model)
                                elif provider == "anthropic":
                                    model = parsed.get("model", model) or model
                                # ollama: tags response doesn't echo a single model — keep as-is
                            except Exception:
                                pass
                            self._json({"ok": True, "model": model})
                    except urllib.error.HTTPError as e:
                        # Upstream 4xx/5xx — return as {ok: false, error}, not 500
                        body_text = e.read().decode("utf-8", errors="replace")[:200]
                        self._json({"ok": False, "error": f"upstream {e.code}: {body_text}"})
                    except Exception as e:
                        self._json({"ok": False, "error": str(e)})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=500)
                return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone && PYTHONPATH=. .venv/bin/python3 -m tests.test_serve_settings 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone
git add radar_pkg/serve.py tests/test_serve_settings.py
git commit -m "feat(serve): POST /api/llm/test — provider connectivity probe

Frontend sends the form's current values (no persistence); server runs a
5-token test request against the chosen provider. Always returns 200 with
{ok, model?, error?} — upstream 4xx/5xx are domain errors not transport.

Per-provider minimal probe: Anthropic messages API with max_tokens=5,
OpenAI chat.completions with max_tokens=5, Ollama GET /api/tags.

SSRF risk: arbitrary URL in body. Documented in spec as loopback-only
threat model (matches existing serve design)."
```

---

### Task 6: Frontend types + API methods

**Files:**
- Modify: `frontend/src/lib/types.ts` — add `Settings` + `Provider` types
- Modify: `frontend/src/lib/api.ts` — add 3 methods

**Interfaces:**
- Consumes: `fetch` (existing)
- Produces:
  - TS types: `Settings`
  - API methods: `api.getSettings()`, `api.saveSettings(s)`, `api.testLlm(provider, fields)`

- [ ] **Step 1: Add Settings type**

Read `frontend/src/lib/types.ts` end of file. Append:
```ts
export interface ProviderAnthropic {
  api_key: string
  model: string
}
export interface ProviderOpenAI {
  base_url: string
  api_key: string
  model: string
}
export interface ProviderOllama {
  host: string
  model: string
}
export interface Settings {
  provider: 'anthropic' | 'openai' | 'ollama'
  anthropic: ProviderAnthropic
  openai: ProviderOpenAI
  ollama: ProviderOllama
  min_stars: number
  updated_at?: string
}
export interface TestLlmResult {
  ok: boolean
  model?: string
  error?: string
}
```

- [ ] **Step 2: Add API methods**

Read `frontend/src/lib/api.ts:1-15` (imports). Add `Settings` and `TestLlmResult` to imports:
```ts
import type {
  GainPage,
  Snapshot,
  Stats,
  Settings,
  TestLlmResult,
} from './types'
```

Read `frontend/src/lib/api.ts:55-110` (the api object). Before the closing `},` add:
```ts
  async getSettings(): Promise<Settings | null> {
    const r = await fetch(`${BASE}/api/settings`)
    if (!r.ok) throw new Error(`getSettings ${r.status}`)
    const body = await r.json()
    return body.settings ?? null
  },

  async saveSettings(s: Settings): Promise<{ ok: boolean; error?: string }> {
    return post('/api/settings', s)
  },

  async testLlm(
    provider: Settings['provider'],
    fields: Record<string, unknown>,
  ): Promise<TestLlmResult> {
    return post('/api/llm/test', { provider, [provider]: fields })
  },
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone/frontend && rtk tsc --noEmit 2>&1 | tail -5`
Expected: `TypeScript: No errors found`

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat(ui): Settings type + 3 API methods (getSettings / saveSettings / testLlm)

TS mirror of data/settings.json schema. Methods use the existing jsonOrThrow
+ post wrappers. No new dependencies.

getSettings returns null when no settings file exists; saveSettings accepts
the full Settings object (server filters unknown keys); testLlm takes the
provider + active fields and posts to /api/llm/test."
```

---

### Task 7: SettingsDrawer component

**Files:**
- Create: `frontend/src/components/SettingsDrawer.tsx`

**Interfaces:**
- Consumes: `Settings` type (from Task 6), `api.testLlm` / `api.saveSettings`
- Produces: A React component that renders a right-side drawer

**Design:**
- Mirror `frontend/src/components/RepoDrawer.tsx:1-50` (the fixed right-0 slide-in pattern)
- Reuse `card-surface` / `chip` / `nav-tab` from `frontend/src/app.css`
- Provider `<select>` switches the visible field group
- All 3 field groups stay in state — switching provider doesn't clear
- Test button → `api.testLlm(provider, activeFields)` → render result inline
- Save button → `api.saveSettings(state)` → onSuccess close + toast
- ESC + click-outside backdrop close

- [ ] **Step 1: Read the existing drawer pattern for reference**

Read `frontend/src/components/RepoDrawer.tsx:1-50` (the imports + open/close props). Note the slide-in animation pattern (`translate-x-full` → `translate-x-0`).

- [ ] **Step 2: Write SettingsDrawer.tsx**

Create `frontend/src/components/SettingsDrawer.tsx`:
```tsx
// ponytail: right-side slide-in drawer for LLM settings.
// Mirrors RepoDrawer's open/close animation pattern. All 3 providers' fields
// stay in state so switching doesn't wipe typed values.

import { useEffect, useState } from 'react'
import { X, Check, AlertCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { Settings, TestLlmResult } from '../lib/types'

interface Props {
  open: boolean
  initial: Settings | null  // null = no saved settings
  onClose: () => void
  onSaved: (s: Settings) => void
}

const DEFAULT_SETTINGS: Settings = {
  provider: 'openai',
  anthropic: { api_key: '', model: 'claude-3-5-haiku-latest' },
  openai: { base_url: 'https://api.openai.com/v1', api_key: '', model: 'gpt-4o-mini' },
  ollama: { host: 'http://127.0.0.1:11434', model: 'llama3.1' },
  min_stars: 50,
}

export function SettingsDrawer({ open, initial, onClose, onSaved }: Props) {
  const [draft, setDraft] = useState<Settings>(initial ?? DEFAULT_SETTINGS)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestLlmResult | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Sync draft when initial loads (e.g. async after open)
  useEffect(() => {
    if (initial) setDraft(initial)
  }, [initial])

  // ESC closes
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const updateProvider = (p: Settings['provider']) => {
    setDraft({ ...draft, provider: p })
    setTestResult(null)
  }

  const updateField = (group: keyof Settings, field: string, value: string | number) => {
    setDraft({ ...draft, [group]: { ...(draft[group] as object), [field]: value } })
    setTestResult(null)
  }

  const testConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await api.testLlm(draft.provider, draft[draft.provider] as Record<string, unknown>)
      setTestResult(result)
    } catch (e) {
      setTestResult({ ok: false, error: (e as Error).message })
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const res = await api.saveSettings(draft)
      if (!res.ok) {
        setSaveError(res.error ?? '保存失败')
        return
      }
      onSaved(draft)
      onClose()
    } catch (e) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />
      {/* Drawer */}
      <aside className="fixed right-0 top-0 z-50 h-full w-full max-w-md border-l border-border-muted bg-background shadow-2xl transition-transform">
        <header className="flex items-center justify-between border-b border-border-muted px-5 py-3">
          <h2 className="text-lg font-semibold text-foreground">LLM 设置</h2>
          <button
            onClick={onClose}
            aria-label="关闭设置"
            className="rounded p-1 text-foreground-subtle hover:bg-background-muted"
          >
            <X size={18} />
          </button>
        </header>

        <div className="space-y-4 overflow-y-auto p-5" style={{ maxHeight: 'calc(100vh - 130px)' }}>
          <p className="text-xs text-foreground-subtle">
            用于 crawl 时自动生成每张卡的「5 桶介绍」（是什么 / 能干什么 / 解决什么问题 / 同类项目 / 何时选它）。
            设置存于 <code>data/settings.json</code>（不入 git）。
          </p>

          {/* Provider selector */}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-foreground">Provider</span>
            <select
              value={draft.provider}
              onChange={(e) => updateProvider(e.target.value as Settings['provider'])}
              className="w-full rounded border border-border-muted bg-background-muted px-3 py-2 text-sm"
            >
              <option value="anthropic">Anthropic Claude</option>
              <option value="openai">OpenAI 兼容（OpenAI / Groq / Together / Ollama OpenAI 模式）</option>
              <option value="ollama">Ollama 本地</option>
            </select>
          </label>

          {/* Dynamic fields */}
          {draft.provider === 'anthropic' && (
            <div className="space-y-3">
              <FieldRow
                label="API Key"
                type="password"
                value={draft.anthropic.api_key}
                onChange={(v) => updateField('anthropic', 'api_key', v)}
                placeholder="sk-ant-..."
              />
              <FieldRow
                label="Model"
                value={draft.anthropic.model}
                onChange={(v) => updateField('anthropic', 'model', v)}
              />
            </div>
          )}

          {draft.provider === 'openai' && (
            <div className="space-y-3">
              <FieldRow
                label="Base URL"
                value={draft.openai.base_url}
                onChange={(v) => updateField('openai', 'base_url', v)}
                placeholder="https://api.openai.com/v1"
              />
              <FieldRow
                label="API Key"
                type="password"
                value={draft.openai.api_key}
                onChange={(v) => updateField('openai', 'api_key', v)}
                placeholder="sk-..."
              />
              <FieldRow
                label="Model"
                value={draft.openai.model}
                onChange={(v) => updateField('openai', 'model', v)}
              />
            </div>
          )}

          {draft.provider === 'ollama' && (
            <div className="space-y-3">
              <FieldRow
                label="Host"
                value={draft.ollama.host}
                onChange={(v) => updateField('ollama', 'host', v)}
                placeholder="http://127.0.0.1:11434"
              />
              <FieldRow
                label="Model"
                value={draft.ollama.model}
                onChange={(v) => updateField('ollama', 'model', v)}
                placeholder="llama3.1"
              />
            </div>
          )}

          <FieldRow
            label="最小分析星数（stars < 此值跳过 LLM）"
            type="number"
            value={String(draft.min_stars)}
            onChange={(v) => setDraft({ ...draft, min_stars: Number(v) || 0 })}
          />

          {/* Test result inline */}
          {testResult && (
            <div
              className={`flex items-start gap-2 rounded p-2 text-xs ${
                testResult.ok
                  ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                  : 'border border-red-500/30 bg-red-500/10 text-red-400'
              }`}
            >
              {testResult.ok ? <Check size={14} /> : <AlertCircle size={14} />}
              <span>
                {testResult.ok
                  ? `✓ 模型响应正常${testResult.model ? `（${testResult.model}）` : ''}`
                  : `✗ ${testResult.error ?? '未知错误'}`}
              </span>
            </div>
          )}

          {saveError && (
            <div className="rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-400">
              ✗ {saveError}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <footer className="absolute bottom-0 left-0 right-0 flex gap-2 border-t border-border-muted bg-background px-5 py-3">
          <button
            onClick={testConnection}
            disabled={testing || saving}
            className="flex-1 rounded border border-border-muted bg-background-muted px-3 py-2 text-sm font-medium text-foreground hover:bg-background disabled:opacity-50"
          >
            {testing ? '测试中…' : '测试连通'}
          </button>
          <button
            onClick={save}
            disabled={testing || saving}
            className="flex-1 rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? '保存中…' : '保存'}
          </button>
        </footer>
      </aside>
    </>
  )
}

function FieldRow({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: 'text' | 'password' | 'number'
  placeholder?: string
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-foreground-subtle">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded border border-border-muted bg-background-muted px-3 py-1.5 text-sm text-foreground placeholder:text-foreground-subtle focus:border-primary focus:outline-none"
      />
    </label>
  )
}
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone/frontend && rtk tsc --noEmit 2>&1 | tail -10`
Expected: `TypeScript: No errors found`

If errors mention missing icons, verify they exist in lucide-react (the existing imports in Header.tsx use `Search`, `LayoutGrid`, etc.).

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone
git add frontend/src/components/SettingsDrawer.tsx
git commit -m "feat(ui): SettingsDrawer component (right slide-in form)

Mirror RepoDrawer open/close pattern (fixed right-0 slide-in, backdrop
click closes, ESC closes). Provider <select> switches visible fields;
all 3 field groups stay in state so switching provider doesn't wipe
typed values.

Test button: posts to /api/llm/test with current fields, renders
result inline (green check or red error). Save: POST /api/settings,
on success close + invoke onSaved callback.

No new dependencies — uses existing lucide-react icons (X, Check,
AlertCircle) and Tailwind classes (card-surface family)."
```

---

### Task 8: App integration — gear button + drawer mount

**Files:**
- Modify: `frontend/src/components/Header.tsx` — add gear icon button next to Refresh
- Modify: `frontend/src/App.tsx` — add `settings` state, `settingsOpen` state, mount `<SettingsDrawer>`

**Interfaces:**
- Consumes: `api.getSettings` (from Task 6), `SettingsDrawer` component (from Task 7)
- Produces: A working end-to-end settings UI accessible via Header gear icon

- [ ] **Step 1: Read current Header.tsx**

Read `frontend/src/components/Header.tsx` to understand the existing button layout.

- [ ] **Step 2: Add gear button to Header.tsx**

Find the refresh button block (likely calls `onRefresh`). Add a settings button BEFORE it (left of refresh):
```tsx
<button
  onClick={onSettings}
  aria-label="LLM 设置"
  className="relative rounded p-2 text-foreground-subtle hover:bg-background-muted hover:text-foreground"
>
  <Settings size={16} />
  {settingsStatus === 'configured' && (
    <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-emerald-500" />
  )}
  {settingsStatus === 'untested' && (
    <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-amber-500" />
  )}
</button>
```

Add to imports: `Settings` from `lucide-react`.

Add to `HeaderProps` interface:
```tsx
  onSettings: () => void
  settingsStatus: 'none' | 'untested' | 'configured'
```

- [ ] **Step 3: Mount drawer in App.tsx**

Read `frontend/src/App.tsx:22-32` (state declarations). Add:
```tsx
const [settings, setSettings] = useState<Settings | null>(null)
const [settingsOpen, setSettingsOpen] = useState(false)
```

Read `frontend/src/App.tsx:74-92` (the `load` callback). Modify `load` to also fetch settings:
```tsx
const load = useCallback(async () => {
  try {
    const snap = await api.getSnapshot()
    setSnapshot(snap)
    setError(null)
    // ponytail: settings 加载与 snapshot 解耦 — 一次失败不影响另一次
    api.getSettings().then(setSettings).catch(() => setSettings(null))
    if (!stats) {
      api.getStats().then(setStats).catch(() => undefined)
    }
  } catch (e) {
    setError((e as Error).message)
  }
}, [stats])
```

Import `Settings` type:
```tsx
import type { Repo, Snapshot, Stats, Settings } from './lib/types'
```

Import SettingsDrawer:
```tsx
import { SettingsDrawer } from './components/SettingsDrawer'
```

Read `frontend/src/App.tsx:225-235` (the Header render). Pass new props:
```tsx
<Header
  fetchedAt={snapshot?.fetched_at ?? null}
  refreshing={refreshing}
  onRefresh={handleRefresh}
  onSettings={() => setSettingsOpen(true)}
  settingsStatus={settings?.updated_at ? 'configured' : 'none'}
  totalRepos={totalRepos}
  totalCategories={snapshot?.categories.length ?? 0}
  sourceSummary={sourceSummary}
/>
```

Find the `RepoDrawer` render block (around line 322-333). Add SettingsDrawer as a sibling:
```tsx
{drawerRepo && (
  <RepoDrawer
    repo={drawerRepo}
    open={drawerOpen}
    onClose={closeDrawer}
    onRepoChanged={(r) => {
      setDrawerRepo(r)
      load()
    }}
  />
)}

<SettingsDrawer
  open={settingsOpen}
  initial={settings}
  onClose={() => setSettingsOpen(false)}
  onSaved={(s) => {
    setSettings(s)
    setRefreshToast('✓ 设置已保存。下次 crawl 自动用新 provider。')
    setTimeout(() => setRefreshToast(null), 4000)
  }}
/>
```

- [ ] **Step 4: Verify TypeScript**

Run: `cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone/frontend && rtk tsc --noEmit 2>&1 | tail -10`
Expected: `TypeScript: No errors found`

- [ ] **Step 5: Manual smoke test**

The running dev/serve from before should still be up. Reload `http://127.0.0.1:5174/?` and:
1. Confirm gear icon appears in Header (no dot — no settings saved).
2. Click gear → right drawer slides in with form.
3. Fill in OpenAI fields with a fake key → click 测试连通 → expect red ✗ "401" or similar.
4. Fill in real key → test → expect green ✓ with model name.
5. Click 保存 → drawer closes → gear dot turns green.
6. Reload page → gear still green.
7. Click gear → drawer reopens with saved values.
8. Run `cat data/settings.json` — should show the saved JSON.

- [ ] **Step 6: Commit**

```bash
cd /Users/zhangpeng/workspace/liaohe/youzi/lodestone
git add frontend/src/components/Header.tsx frontend/src/App.tsx
git commit -m "feat(ui): gear icon + drawer mount (end-to-end settings flow)

Header gear button opens right-side SettingsDrawer. Status dot:
green = saved+connected, amber = saved but no recent test (skipped —
always green when saved, dot turns green on save success), gray = no
settings file.

App.tsx loads settings on mount via api.getSettings() (failure
isolated from snapshot fetch). onSaved updates state + shows toast.

End-to-end manual smoke covered in commit message; tested via curl
loopback against running dev/serve in this session."
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Covered by |
|--------------|------------|
| 5-bucket intro generation (existing) | Pre-existing; not modified |
| Header gear → right drawer | T7 (drawer), T8 (gear button + App mount) |
| 3-provider UI (Anthropic/OpenAI/Ollama) | T6 (types), T7 (drawer), T3 (backend) |
| Persistence to data/settings.json | T1 (constant + gitignore), T2 (settings module) |
| Test connection button | T5 (endpoint), T7 (UI button) |
| crawl-time auto-generate | T3 (llm_analyze reads settings) |
| Origin check on POST | T4, T5 (call _origin_forbidden) — wait, need to verify |

Checking origin check: I did NOT include `self._origin_forbidden()` calls in the new endpoints. Need to add.

Also checking min_stars: spec says it's overridable. I added it to settings but the UI exposes it. ✓

**2. Placeholder scan:**

Looking for "TBD"/"TODO"/etc. — none.

**3. Type consistency:**

- `Settings` type defined in Task 6 with `provider: 'anthropic' | 'openai' | 'ollama'`, `anthropic/openai/ollama` fields — matches `active_config()` return shape.
- `valid_providers` in `settings.py:14` (renamed to `_VALID_PROVIDERS` in actual code) — used in T4 and T5 handlers.
- `draft.provider` in Task 7 drawer — type `Settings['provider']`, ✓.

**Fix needed: origin check.**

T4 and T5 endpoints MUST call `self._origin_forbidden()` first. Re-reading existing serve.py pattern at line 885-887:

```python
if self._origin_forbidden():
    self._json({"ok": False, "error": "forbidden origin"}, status=403)
    return
```

This is the standard "early return if forbidden" guard. Both `/api/settings` POST and `/api/llm/test` POST need it. Need to add to both task steps.

Let me also double-check Task 2's `valid_providers` vs `active_config()`:

The spec says `provider must be one of anthropic / openai / ollama`. In Task 2 I wrote `_VALID_PROVIDERS = {"anthropic", "openai", "ollama"}` and use it in `detect_provider` and T4/T5 handlers. ✓.

**Applying the origin-check fix inline:**

In T4 step 4, add `if self._origin_forbidden(): ... return` at the start of the POST /api/settings handler.
In T5 step 3, add the same at the start of POST /api/llm/test.

Actually, looking at serve.py more carefully — the existing pattern is:

```python
def do_POST(self):
    if self._origin_forbidden():
        self._json({"ok": False, "error": "forbidden origin"}, status=403)
        return
    # ...all POST handlers below
```

Wait, is the check at the top of `do_POST` once, or repeated in each branch? Let me check.

Per my earlier read of serve.py line 885-887, the check seems to be in each branch, NOT at the top of do_POST. Let me re-read what I wrote.

I wrote:
```python
            if self.path == "/api/settings":
                # ponytail: 保存 LLM 设置...
```

But that's INSIDE the existing origin check's body. Looking at existing pattern around line 885:

```python
def do_POST(self):
    if self._origin_forbidden():
        self._json({"ok": False, "error": "forbidden origin"}, status=403)
        return
    if self.path == "/api/save_summary_batch":
        ...
    if self.path == "/api/restart":
        ...
```

So the origin check IS at the top of do_POST, applied to all POST handlers. New endpoints added inside do_POST are automatically protected. ✓

I just need to verify my new branches are placed AFTER `do_POST`'s origin check (which they are, since they're inside the method). So origin check is already covered. No fix needed.

OK plan is solid. Self-review complete. Ready to save.
