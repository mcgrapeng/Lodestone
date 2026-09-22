# Lodestone v2.x — Batch Category Install + 7-Source Marquee

**Date**: 2026-09-22
**Status**: Design approved by user

## Problem

1. **No batch action**: User has to click 30+ dots individually to install a whole category.
2. **Marquee shows only 4 sources**: After FU-1 added awesome_lists + hackernews_ai, the data exists but the UI doesn't surface it.

## Evidence

- `frontend/src/lib/filters.ts:7` — `SourceKind = 'github' | 'huggingface' | 'mcp' | 'arxiv' | 'other'` — no new source kinds.
- `frontend/src/components/Header.tsx:130` — marquee hardcodes the 4 sources.
- `frontend/src/App.tsx:251-273` — `sourceCounts` and `sourceSummary` only iterate the 4 sources.
- `radar_pkg/serve.py:1539-1573` — `/api/install` handler takes one repo at a time.
- `radar_pkg/serve.py:1645-1671` — `/api/update` (single repo update), `/api/uninstall` (single repo, all CLIs).
- `radar_pkg/serve.py:1682+` — `/api/install-cli` (existing, see below) and `/api/upgrade-all` (background Popen).
- `radar_pkg/core.py` `sources/awesome_lists.py`, `sources/hackernews_ai.py` — exist and crawl, but never surface counts.

## Approach (Recommended, Approved)

### Feature 1: Batch install/uninstall per category (Categories tab only)

Two new endpoints (fire-and-forget background threads; reuse `/api/install/status` polling):

| Endpoint | Body | Behavior |
|---|---|---|
| `POST /api/install_category` | `{category_id, target, except?}` | Spawns thread, loops `cat.repos` where `is_skill=true`, calls `install_skill_from_github(name, url, targets=[target])` per repo. Skip + log on individual failure (no abort). Writes progress to `data/install_status.json`. |
| `POST /api/uninstall_category` | `{category_id, target, except?}` | Same pattern: loops `cat.repos`, calls `uninstall_skill(name, targets=[target])`. |

**Status write** via existing `core.write_install_status()` — fields:
- `computing: true/false`
- `current: "<cli>-<action> <repo-name>"`
- `current_index: int`
- `total: int`
- `started_at: ISO`
- `error: "<last-error>" | null`
- `error_count: int` (NEW field — sub-failures, doesn't abort)

### Feature 2: Marquee shows all 7 sources (currently only 4)

**Backend change**: `/api/data` response gains `sources: [...]`:
```json
{
  "sources": [
    {"name": "github",         "label": "GitHub",   "count": 542},
    {"name": "huggingface",    "label": "HF",       "count": 59},
    {"name": "mcp",            "label": "MCP",      "count": 0},
    {"name": "arxiv",          "label": "arXiv",    "count": 24},
    {"name": "awesome_lists",   "label": "Awesome",  "count": 1937},
    {"name": "hackernews_ai",   "label": "HN",       "count": 12}
  ],
  ...
}
```

Count sources:
- github/huggingface/mcp/arxiv: existing `sourceCounts` tally in `App.tsx`
- awesome_lists: `sources/awesome_lists.py` exposes `_LISTS` size (existing module-level). The crawl emits the count via the new status dict — `len(_seen_in_` set after crawl.
- hackernews_ai: same pattern.

**`core.py` `data-provenance.json`** writer adds:
- `sources_count` = `{name: count}` dict (replacing the existing flat `sources: [name1, name2, ...]` list with name + count)

**Frontend change**:
- `frontend/src/lib/filters.ts`: extend `SourceKind` to `'github' | 'huggingface' | 'mcp' | 'arxiv' | 'awesome_lists' | 'hackernews_ai' | 'other'`
- `frontend/src/App.tsx`: extend `SourceCounts` to include new keys; extend `sourceSummary` to emit `Awesome: <n>` and `HN: <n>`
- `frontend/src/components/Header.tsx`: marquee text → `→ GitHub: {n} · HF: {n} · MCP: {n} · arXiv: {n} · Awesome: {n} · HN: {n} · last crawl <ago> ·`

## Architecture

```
Frontend
├── CategoryBrowser.tsx      ← + toolbar with [target] [全装] [全卸] [状态 X/Y]
│                                polls /api/install/status every 2s while computing
├── Header.tsx                ← marquee text expanded (6 sources instead of 4)
└── lib/filters.ts            ← SourceKind extended
Backend
├── serve.py
│   ├── /api/install_category     NEW: POST → spawn thread → loop cat.repos
│   ├── /api/uninstall_category   NEW: same pattern
│   ├── /api/install/status       EXISTING: reused for polling
│   └── /api/data                 MOD: add `sources: [...]` array
└── radar_pkg/sources/
    ├── awesome_lists.py        EXPORT _get_count() -> int (read internal _seen set size)
    └── hackernews_ai.py        EXPORT _get_count() -> int (same pattern)

core.py
└── data-provenance.json        schema: add `sources_count: {name: n}`
```

## Acceptance Criteria

### Feature 1
- Click [全装到: codex] on a category → all `is_skill=true` repos in that category install to codex (skip non-skill repos silently).
- Status updates in toolbar as installs complete: `12/30 ✓`
- A repo that already exists at codex with `force_update=false` skips (no duplicate symlink).
- A repo that fails (clone error, rate limit) is logged + counted in `error_count`, but does not abort the batch.
- After batch, `/api/local` reflects all newly installed skills; RepoCard dots fill for the target CLI.
- Per-target uninstall works: only that CLI's symlink is removed, others preserved.

### Feature 2
- `/api/data` returns `sources` array with all 6 names + counts.
- Header marquee shows 6 sources.
- Awesome + HN counts are non-zero (sanity-check: they were added in FU-1 and crawled).
- `data-provenance.json` `sources_count` matches what marquee shows (cross-source-of-truth check).

## Test Coverage Targets

| Test | Asserts |
|---|---|
| `tests/test_install_category.py` (NEW) | Install endpoint spawns thread; thread installs each repo in category; existing installs skipped; failures logged but don't abort; status JSON updated |
| `tests/test_sources_count.py` (NEW) | /api/data returns 6 sources with correct counts; data-provenance.json sources_count matches |
| `tests/test_install_per_target.py` (extend) | New tests for batch uninstall — only target removed, others preserved |

## Out of Scope (deferred)

- Batch button in RepoDrawer (user picked categories only)
- Batch button in LocalTab (user picked categories only)
- Inline source labels in hot_now cards (separate feature)
- Awesome/HN data merged into hot_now count (kept separate)

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 30-repo batch takes 150s | Medium | UI timeout | Fire-and-forget + poll pattern (like `/api/upgrade-all`) |
| One repo's `gh api` rate limit fails mid-batch | Medium | Partial state | Skip + log + continue; report `error_count` in status |
| Two simultaneous batch requests race on `INSTALL_LOCK` | Low | 409 error | Lock is non-reentrant; second request returns clean error |
| Backend `/api/data` payload size grows with `sources` field | Low | Network | Field is small (~6 entries × 2 keys = 200 bytes max) |
| `filters.ts` `SourceKind` mismatch between frontend/backend | Low | TS error | `SourceKind` is frontend-only; backend uses `repo.source` as free string |

## Global Constraints

- Same as parent plan: stdlib-only tests, no breaking API changes, no new DB schema
- All `pnytail:` comments use lowercase style matching existing code
- Tests use `unittest` (no pytest)