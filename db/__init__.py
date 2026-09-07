"""ai_radar.db — Postgres helpers. Uses pg8000 (pure Python, no C extension).
ponytail: PG is optional — if pg8000 / Postgres unreachable, fall back to no-op so
`radar.py serve` can still render /api/local (skills / plugins / CLIs) without PG.
"""

import os as _os

# ponytail: explicit JSON-only override — set AI_RADAR_NO_PG=1 to skip PG entirely.
_FORCE_JSON = _os.environ.get("AI_RADAR_NO_PG", "").lower() in (
    "1", "true", "yes", "on"
)

try:
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

    _DB_OK = not _FORCE_JSON
    if _FORCE_JSON:
        import sys as _sys

        print(
            "[db] AI_RADAR_NO_PG=1 set — running in JSON-only mode",
            file=_sys.stderr,
        )
except ImportError as _exc:
    import sys as _sys

    print(
        f"[db] pg8000 unavailable ({_exc}); falling back to JSON-only mode",
        file=_sys.stderr,
    )
    _DB_OK = False
    connect = ensure_database = ensure_schema = None  # type: ignore
    SCHEMA_PATH = DSN_DEFAULTS = None  # type: ignore
    upsert_repos = replace_categories = snapshot_stars = set_trending = None  # type: ignore
    query_top_5k = query_hot_now = query_categories = query_gain = None  # type: ignore

__all__ = [
    "connect",
    "ensure_database",
    "ensure_schema",
    "SCHEMA_PATH",
    "DSN_DEFAULTS",
    "upsert_repos",
    "replace_categories",
    "snapshot_stars",
    "set_trending",
    "query_top_5k",
    "query_hot_now",
    "query_categories",
    "query_gain",
]
