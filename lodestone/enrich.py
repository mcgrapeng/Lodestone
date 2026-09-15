"""Enrichment state — tracks whether host LLM has run the first 5-bucket pass.

State file: data/.enriched_at — single-line ISO timestamp.
  - absent  → host LLM should run enrichment on next /yz:ai call
  - present → host LLM should skip enrichment (data already populated)

Host LLM writes this file after a successful enrichment pass.
Re-enrichment: user runs `rm data/.enriched_at` or POST /api/enrich/reset.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

# ponytail: DATA path = repo-root/data — compute from file location rather
# than depending on a top-level core module that doesn't exist.
_DATA = Path(__file__).resolve().parent.parent / "data"


def enriched_path() -> Path:
    return _DATA / ".enriched_at"


def is_enriched() -> bool:
    return enriched_path().exists()


def enriched_at() -> str | None:
    p = enriched_path()
    return p.read_text().strip() if p.exists() else None


def mark_enriched() -> str:
    p = enriched_path()
    ts = datetime.now(timezone.utc).isoformat()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(ts)
    return ts


def clear() -> None:
    p = enriched_path()
    if p.exists():
        p.unlink()
