# Migrating from Lodestone 1.x to 2.0

Lodestone 2.0 keeps 1.x's data on disk. To migrate:

1. `pip install -e .` (new package)
2. `python3 -m lodestone migrate` — reads `data/latest.json` + `data/settings.json` → 2.0 PG tables
3. `python3 -m lodestone serve` — starts FastAPI on 8765
4. Frontend at `frontend/dist/` or `npm run dev` — unchanged (calls same `/api/settings` endpoint)

## What changed
- New plugin system: data sources, scorers, notifiers are entry_points
- New: `/api/notifications`, `/api/plugins/{name}/config`, `/api/plugins/{name}/test`
- Removed: monolithic `radar.py` facade (replaced by `python3 -m lodestone {crawl,serve,plugin-list,migrate}`)
- `data/settings.json` still works (1.x compat)

## What did NOT change
- 4 data sources (GitHub / HF / MCP / arXiv) — same coverage
- 20 categories — same definitions
- LLM analysis — same prompt
- `data/settings.json` — same path, same JSON shape
