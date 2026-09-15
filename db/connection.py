"""PG connection helpers + first-boot setup. All defs are pure functions."""

import os
import re
from pathlib import Path

# ponytail: 2026-09 — 单一 .env 加载源（env_loader 是项目根下 30 行 stdlib 实现）。
# radar.py main 也调一次 load_env()（幂等、setdefault 语义、shell 优先），删除旧的 _load_dotenv。
# 这里必须先于 pg8000 import，否则 PGPASSWORD/PGDATABASE 还没填。
from env_loader import load_env  # noqa: E402
load_env()

import pg8000.dbapi as pg  # noqa: E402  (must run after env_loader)
from pg8000.converters import JSONB as _JSONB_OID, PG_TYPES as _PG_TYPES, json_in as _json_in  # noqa: E402

# ponytail: 2026-09 — 防御性 JSONB 类型适配器注册。pg8000 ≥1.30 默认 PG_TYPES[3802]=json_in
# （loads 解析为 dict），但旧版本可能漏注册导致 JSONB 列读回 str — 5 桶渲染前端全空。
# 这里 idempotent 注册一遍（已注册则覆盖回相同 callable，无副作用）。
if _PG_TYPES.get(_JSONB_OID) is not _json_in:
    _PG_TYPES[_JSONB_OID] = _json_in

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
