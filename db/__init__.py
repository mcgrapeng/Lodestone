"""ai_radar.db — Postgres helpers. Uses pg8000 (pure Python, no C extension)."""
from .connection import (
    connect,
    ensure_database,
    ensure_schema,
    SCHEMA_PATH,
    DSN_DEFAULTS,
)
from .repos import (
    upsert_repos,
    replace_categories,
    snapshot_stars,
    set_trending,
    query_top_5k,
    query_hot_now,
    query_categories,
    query_gain,
)

__all__ = [
    "connect", "ensure_database", "ensure_schema", "SCHEMA_PATH", "DSN_DEFAULTS",
    "upsert_repos", "replace_categories", "snapshot_stars", "set_trending",
    "query_top_5k", "query_hot_now", "query_categories", "query_gain",
]
