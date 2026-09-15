# LLM Settings UI — Design Spec

**Date**: 2026-09-14
**Author**: opencode (grill-me session)
**Status**: approved by user, pending implementation

## Problem

Lodestone's 5-bucket project intros (`analysis_5d`: what / can_do / problem / alternatives / when_to_use)
are currently generated one of two ways:

1. **crawl-time LLM** via `radar_pkg/llm_analyze.py` — fires automatically during `radar.py crawl`,
   driven by env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
   `OLLAMA_HOST`, `OLLAMA_MODEL`, `LLM_MIN_STARS`).
2. **on-demand via `/yz:ai` skill** — the host LLM (Claude Code / Codex) reads cached README,
   generates 5 buckets, and `POST /api/save_summary_batch`.

Both paths require the user to edit `.env` or rely on the host skill. There is no UI to
configure an LLM provider from inside the dashboard. The user wants a settings drawer that
exposes the crawl-time LLM configuration so they can switch providers / endpoints without
leaving the browser.

## Goals

- Configure LLM provider + endpoint + key + model from the dashboard (gear icon → right drawer).
- Settings persist to disk so the crawl process can read them on the next run.
- Crawl-time auto-generation reuses the existing `analyze_many` path; no new orchestration.
- Test-connection button to validate config without running a full crawl.

## Non-Goals

- Per-card "regenerate now" button — covered by the existing `/api/save_summary_batch`
  endpoint + `/yz:ai` skill. Not in scope.
- API key encryption via OS keychain — out of scope; key stored plaintext on local disk
  (acceptable for dev workflow; production deployments should use env vars or keychain).
- Multi-provider selection (run two providers in parallel) — single active provider.
- Async progress UI for crawl-time LLM analysis — existing crawl log line
  `✓ llm analysis: N/M ok` is sufficient.

## Decisions (from brainstorming Q&A)

| Question | Choice | Rationale |
|----------|--------|-----------|
| Trigger model | **A. Settings + crawl-time auto-generate** | Lowest cost, broadest coverage. No per-card click cost. |
| Provider scope | **B. All 3 backends exposed** (Anthropic / OpenAI compat / Ollama) | Anthropic is what most devs try first; Ollama covers local; OpenAI compat covers Groq/Together/vLLM. |
| UI placement | **A. Header gear → right drawer** | Matches RepoDrawer pattern (right-side slide-in). Doesn't pollute TabNav. |
| Persistence | **A. Disk JSON** (`data/settings.json`, gitignored) | Crawl process is separate from serve; needs cross-process access. localStorage won't reach crawl. |

## Architecture

```
Frontend (React)
  Header ⚙️ button → SettingsDrawer (right slide-in)
    ├── Provider <select>: anthropic | openai | ollama
    ├── Dynamic fields (per provider)
    ├── Test connection button (→ POST /api/llm/test)
    └── Save (→ POST /api/settings)
                      │ HTTPS loopback
                      ▼
radar.py serve (8765)
  GET  /api/settings       → {provider, fields, status}
  POST /api/settings       → write data/settings.json (atomic)
  POST /api/llm/test       → ping chosen provider, return {ok, model?, error?}
                      │
                      ▼ shared file
data/settings.json (.gitignore)
                      │
                      ▼
radar.py crawl (spawned by /api/crawl)
  llm_analyze.detect_provider() reads settings.json → env fallback
  analyze_many(repos) — unchanged orchestration
```

## Data Schema

### `data/settings.json`

```json
{
  "provider": "openai",
  "anthropic": {
    "api_key": "sk-ant-...",
    "model": "claude-3-5-haiku-latest"
  },
  "openai": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-...",
    "model": "gpt-4o-mini"
  },
  "ollama": {
    "host": "http://127.0.0.1:11434",
    "model": "llama3.1"
  },
  "min_stars": 50,
  "updated_at": "2026-09-14T12:34:56Z"
}
```

- `provider` selects which group of fields is active.
- All three groups are always present; only the active one is read at call time.
- `min_stars` overrides env `LLM_MIN_STARS`.
- `updated_at` set on every save (server-side ISO 8601).
- File missing → all values fall back to env defaults (backward compatible).

### TS type `Settings`

```ts
type Provider = 'anthropic' | 'openai' | 'ollama'
interface Settings {
  provider: Provider
  anthropic: { api_key: string; model: string }
  openai: { base_url: string; api_key: string; model: string }
  ollama: { host: string; model: string }
  min_stars: number
  updated_at?: string
}
```

## Backend Changes

### New file: `radar_pkg/settings.py` (~75 lines)

```python
"""LLM settings persistence — data/settings.json (gitignored)."""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from radar_pkg import core

_KEYS = {"provider", "anthropic", "openai", "ollama", "min_stars", "updated_at"}


def load() -> dict | None:
    if not core.SETTINGS_PATH.exists():
        return None
    try:
        return json.loads(core.SETTINGS_PATH.read_text())
    except (OSError, ValueError):
        print("[settings] corrupt file, falling back to env", file=sys.stderr)
        return None


def save(d: dict) -> None:
    payload = {k: v for k, v in d.items() if k in _KEYS}
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    core.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = core.SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    tmp.replace(core.SETTINGS_PATH)


def _detect_env_provider() -> str | None:
    """Env-only provider detection (no Ollama probe — saves 2s timeout per call)."""
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
    """Return (provider_name, fields_dict). Settings file wins; env is fallback."""
    s = load() or {}
    provider = s.get("provider") or _detect_env_provider() or "openai"
    fields = (s.get(provider) if s else None) or _env_fields_for(provider)
    return provider, fields
```

### Edit `radar_pkg/core.py`

Add `SETTINGS_PATH = DATA / "settings.json"`.

### Edit `radar_pkg/llm_analyze.py`

Replace `os.environ["ANTHROPIC_API_KEY"]` (line 211) etc. with calls to `settings.active_config()`.

Specifically:

- `detect_provider()` (line 92-107): read `settings.active_config()` first; if config has
  required field, return that provider; else fall through to env probe.
- `_call_anthropic/_call_openai/_call_ollama` (lines 209-263): pull api_key/base_url/host/model
  from the active config, not directly from `os.environ`.
- `_MIN_STARS_FOR_ANALYSIS` (line 72): read from settings, fall back to env.

### Edit `radar_pkg/serve.py`

Add three endpoints in `do_GET`/`do_POST`:

- `GET /api/settings` → `jsonify({...settings, status: {configured: bool, last_error: str|null}})`
- `POST /api/settings` → validate body, call `settings.save(body)`, return `{ok: true}`
- `POST /api/llm/test` → read provider from body, call `detect_provider()` with overrides,
  send a trivial test request (`{"max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]}`),
  return `{ok: true, model: "..."}` or `{ok: false, error: str(e)}`.

Origin check (same `_origin_forbidden()` guard as existing endpoints).

### Edit `radar_pkg/crawl.py`

No code changes. `analyze_many` already calls `detect_provider` and `_dispatch` — both
auto-pick up the new settings source.

### New file `.gitignore`

```
data/settings.json
data/.settings.json.tmp
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

(Yes, we should have had this from day 1; existing tracking of `__pycache__/`, `data/serve.log`
etc. is a pre-existing debt. Don't auto-fix unrelated entries — the scope here is settings.json.
Add a `ponytail:` comment noting the others are pre-existing.)

## Frontend Changes

### Edit `frontend/src/lib/api.ts`

Add:
```ts
async getSettings(): Promise<Settings>
async saveSettings(s: Settings): Promise<{ok: boolean; error?: string}>
async testLlm(p: string, f: object): Promise<{ok: boolean; model?: string; error?: string}>
```

### Edit `frontend/src/lib/types.ts`

Add the `Settings` type (TS mirror of JSON schema).

### New file `frontend/src/components/SettingsDrawer.tsx` (~150 lines)

- Right-side slide-in drawer (mirror `RepoDrawer.tsx`'s fixed/translate pattern).
- Provider `<select>` with 3 options.
- Dynamic field rendering based on provider:
  - anthropic: API Key, Model
  - openai: Base URL, API Key, Model
  - ollama: Host, Model
- All 3 groups are kept in state (switching provider doesn't clear other fields).
- Test connection button: `api.testLlm(provider, activeFields)` → render result inline.
- Save button: `api.saveSettings(state)` → close drawer on success, show error inline.
- ESC closes (mirrors RepoDrawer).
- Click-outside backdrop closes.

### Edit `frontend/src/components/Header.tsx`

- Add gear button (`<Settings />` icon from lucide-react) next to existing refresh button.
- Color dot indicator: green = configured+connected, yellow = configured+untested,
  gray = missing.

### Edit `frontend/src/App.tsx`

- Add state: `settings: Settings | null` (loaded on mount via `api.getSettings()`).
- Add state: `settingsOpen: boolean`.
- Mount `<SettingsDrawer>` (sibling of `<RepoDrawer>`), passing settings + onChange +
  onClose handlers.

### Edit `frontend/src/app.css`

Reuse existing `.card-surface`, `.chip`, drawer animations. No new classes needed if we
mirror `RepoDrawer` styling.

## Data Flow

### First-time setup
1. User opens dashboard. `App` mounts → `api.getSettings()` returns `null` → gear dot is gray.
2. User clicks gear → `SettingsDrawer` opens with `provider: 'openai'` default, fields empty.
3. User fills Base URL (`https://api.openai.com/v1`), API Key (`sk-...`), Model (`gpt-4o-mini`).
4. User clicks Test → `POST /api/llm/test {provider, openai:{base_url,api_key,model}}` →
   server runs a 5-token test call → returns `{ok: true, model: 'gpt-4o-mini-2024-07-18'}` →
   drawer shows green "✓ 模型响应正常" inline.
5. User clicks Save → `POST /api/settings {full state}` → server writes
   `data/settings.json` atomically → returns `{ok: true}` → drawer closes → gear dot
   turns green.
6. User clicks Header "Refresh" → `radar.py crawl` spawns in background.
7. Crawl runs → `_crawl_inner` calls `analyze_many(repos)` → `detect_provider()` reads
   `data/settings.json` → resolves to `openai` with user's config → calls LLM per repo →
   writes `analysis_5d` to README_ZH_CACHE → batch upsert writes to PG/JSON.
8. Next `getSnapshot()` returns repos with `analysis_5d`. `RepoDrawer` renders 5 buckets.

### Subsequent loads
1. `App` mounts → `api.getSettings()` returns saved settings → drawer pre-fills with
   current values on open.

### Switching providers
1. User opens drawer, picks "Ollama" from dropdown.
2. Fields switch to show Host + Model (Anthropic/OpenAI fields hidden but kept in state).
3. User fills `http://127.0.0.1:11434` + `llama3.1`.
4. Test → server probes `http://127.0.0.1:11434/api/tags` → if responds, returns
   `{ok: true, model: 'llama3.1'}`.
5. Save → next crawl uses Ollama.

## Error Handling

| Failure | Behavior |
|---------|----------|
| `data/settings.json` corrupt JSON | `settings.load()` returns None; serve logs `[settings] corrupt file, falling back to env` once at startup; crawl proceeds with env. |
| API key invalid (401/403 from upstream) | `analyze_one` catches exception, returns None (existing); crawl prints `[llm] openai call failed: 401 ...`; affected repo falls back to 3-bucket `summary_sections`. |
| `testLlm` with missing required field | 400 `{ok: false, error: "anthropic.api_key required"}` |
| `saveSettings` write fails (disk full, perms) | 500 `{ok: false, error: str(e)}`; drawer shows "保存失败: ..." |
| OpenAI compat without base_url | 400 from server; UI field gets red border |
| Crawl with settings but no LLM responds | crawl prints warning, skips analysis, analysis_5d stays null/old; UI shows 3-bucket fallback (existing behavior) |

## Testing

### New `tests/test_settings.py`

Uses a tmp dir for `SETTINGS_PATH` (override via monkey-patch) so it doesn't touch real
`data/settings.json`.

- `test_save_load_roundtrip` — save dict → load → equal
- `test_load_missing_file_returns_none` — no file → None
- `test_load_corrupt_file_returns_none` — invalid JSON → None, no exception
- `test_save_atomic_via_tmp_rename` — write → file exists, no `.tmp` residue
- `test_save_filters_unknown_keys` — extra keys dropped
- `test_active_config_falls_back_to_env` — no file → uses env
- `test_active_config_picks_settings_over_env` — file present → file values win

### New `tests/test_serve_settings.py`

Boots `radar_pkg.serve` on a free port (`port=0` then read `server.server_address[1]`),
uses `urllib.request` for HTTP (no `requests`). Same pattern as the existing stdlib tests.

- `test_get_settings_returns_null_when_no_file`
- `test_post_then_get_roundtrips`
- `test_post_rejects_unknown_field`
- `test_post_validates_required_field`
- `test_llm_test_with_invalid_key_returns_error_not_500`

For `/api/llm/test` with a fake key, the upstream call should fail with a clear error
(401 / connection refused); the test asserts the endpoint returns 200 with
`{ok: false, error: "..."}` rather than a 500.

### Frontend

No new test framework (no vitest installed). UI smoke is manual — see Verification section.

## Verification (manual smoke after implementation)

1. Start `radar.py serve` on 8765.
2. Open `http://127.0.0.1:5174` (Vite) or `:8765` (prod build).
3. Confirm gear icon visible in header, no dot (or gray dot).
4. Open drawer, pick OpenAI, fill in test key, click Test — expect red error.
5. Fix key, click Test — expect green ✓.
6. Save, confirm drawer closes, gear dot turns green.
7. Run `radar.py crawl` (or click Header Refresh).
8. After crawl finishes, open any hot_now repo drawer — confirm 5 buckets rendered.
9. Open gear again — confirm settings persist.

## Risks & Trade-offs

1. **API key plaintext on disk** (per user choice A). Acceptable for dev. Production
   deployments should swap `data/settings.json` for OS keychain or `.env`-only. Out of scope
   for this spec; document in a comment block in `settings.py`.

2. **All 3 providers' fields persisted even when inactive**. Pro: switching provider
   preserves entered fields (no retyping). Con: file has unused fields. Net positive UX.

3. **No server restart needed** when settings change. Crawl subprocess inherits file
   access; next crawl reads fresh. Confirmed safe because `analyze_one` reads settings
   per-call via `detect_provider()` → `active_config()`.

4. **Concurrent settings write race** (UI save + manual `vim data/settings.json`).
   Mitigated by atomic `.tmp + rename`. Two simultaneous saves produce last-writer-wins,
   acceptable for dev.

5. **No CSP for /api/llm/test endpoint**. The endpoint takes an arbitrary provider URL
   in the body — a malicious actor with `127.0.0.1` access could SSRF to internal
   services. Origin check (`_origin_forbidden`) blocks non-loopback browser requests,
   but curl/locally trusted users can still POST any URL. Acceptable given the threat
   model (loopback-only service per existing `serve` design); document with a comment.

## Out of Scope (deferred)

- OS keychain integration (issue separate if needed)
- Per-card "regenerate" button (existing `/api/save_summary_batch` covers this)
- Provider availability probe on drawer open (test button only)
- Auto-detect Ollama on `127.0.0.1:11434` (manual test covers it)
- Settings import/export (manual JSON edit acceptable for dev)

## Implementation Plan

After spec approval, invoke `writing-plans` skill to produce the implementation plan.
