"""PG connection helpers + first-boot setup. All defs are pure functions."""
import os
from pathlib import Path

import pg8000.dbapi as pg

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# ponytail: docker innies-postgres defaults; override via PG* env vars
DSN_DEFAULTS = dict(
    host="127.0.0.1",
    port=5432,
    user="postgres",
    password="zpeng512",
    database="ai_radar",
)


def _dsn(**overrides):
    d = {**DSN_DEFAULTS}
    # env overrides first (so explicit kwargs always win)
    env_map = {
        "host": "PGHOST", "port": "PGPORT",
        "user": "PGUSER", "password": "PGPASSWORD", "database": "PGDATABASE",
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
        host=d["host"], port=d["port"], user=d["user"],
        password=d["password"], database=d["database"],
    )


def ensure_database(admin_db="postgres", **overrides):
    """Create the ai_radar database if it doesn't exist (idempotent)."""
    d = _dsn(database=admin_db, **overrides)
    conn = pg.connect(
        host=d["host"], port=d["port"], user=d["user"],
        password=d["password"], database=admin_db,
    )
    try:
        # ponytail: CREATE DATABASE must run outside a transaction block — open a fresh conn
        conn.autocommit = True
        cur = conn.cursor()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DSN_DEFAULTS["database"],))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{DSN_DEFAULTS["database"]}"')
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
