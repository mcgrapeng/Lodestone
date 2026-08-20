"""PG connection helpers + first-boot setup. All defs are pure functions."""

import os
import re
from pathlib import Path


# ponytail: 5-line .env loader — keeps credentials out of git without adding a dependency.
# Values already present in the environment win (os.environ.setdefault).
def _load_dotenv() -> None:
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


_load_dotenv()

import pg8000.dbapi as pg  # noqa: E402  (must run after dotenv load)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# ponytail: no secrets in code — password comes from PGPASSWORD / .env; empty default
# means "trust auth or explicit env". Override any field via PG* env vars.
DSN_DEFAULTS = dict(
    host="127.0.0.1",
    port=5432,
    user="postgres",
    password=os.environ.get("PGPASSWORD", ""),
    database=os.environ.get("PGDATABASE", "ai_radar"),
)

_DB_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


def _dsn(**overrides):
    d = {**DSN_DEFAULTS}
    # env overrides first (so explicit kwargs always win)
    env_map = {
        "host": "PGHOST",
        "port": "PGPORT",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "database": "PGDATABASE",
    }
    for k, env in env_map.items():
        v = os.environ.get(env)
        if v is not None:
            d[k] = int(v) if k == "port" else v
    # explicit caller overrides win over env
    for k, v in overrides.items():
        if v is not None:
            d[k] = int(v) if k == "port" else v
    return d


def connect(**overrides):
    """Open a pg8000 connection. Caller is responsible for closing."""
    d = _dsn(**overrides)
    return pg.connect(
        host=d["host"],
        port=d["port"],
        user=d["user"],
        password=d["password"],
        database=d["database"],
    )


def ensure_database(admin_db="postgres", **overrides):
    """Create the target database if it doesn't exist (idempotent).
    Target = overrides['database'] (or env/defaults). admin_db = where CREATE DATABASE runs.
    ponytail: target name comes from the FULL env-aware dsn — PGDATABASE used to be
    ignored here, creating/checking the wrong database."""
    target_db = str(_dsn(**overrides)["database"])
    if not _DB_IDENT.match(target_db):
        raise ValueError(f"unsafe database name: {target_db!r}")
    conn_overrides = {k: v for k, v in overrides.items() if k != "database"}
    d = _dsn(database=admin_db, **conn_overrides)
    conn = pg.connect(
        host=d["host"],
        port=d["port"],
        user=d["user"],
        password=d["password"],
        database=admin_db,
    )
    try:
        # ponytail: CREATE DATABASE must run outside a transaction block
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{target_db}"')
        conn.commit()
    finally:
        conn.close()


def ensure_schema(**overrides):
    """Apply db/schema.sql (idempotent CREATE statements)."""
    conn = connect(**overrides)
    try:
        cur = conn.cursor()
        cur.execute(SCHEMA_PATH.read_text())
        conn.commit()
    finally:
        conn.close()
