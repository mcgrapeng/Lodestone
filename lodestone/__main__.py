"""CLI entry — `python3 -m lodestone <subcommand>`."""
from __future__ import annotations
import argparse
import asyncio
import os
import sys

import asyncpg
import uvicorn

from lodestone import __version__
from lodestone.app import create_app
from lodestone.registry import registry
from lodestone.scheduler import scheduler
from lodestone.store import Store
from lodestone import migrate as migrate_mod


async def _cmd_crawl(args):
    registry.discover()
    sources = [args.source] if args.source else [n for n, _ in registry.list_by_kind("source")]
    for name in sources:
        plugin = registry.get(name)
        if plugin is None:
            print(f"  ! unknown source: {name}", file=sys.stderr)
            continue
        print(f"  · crawling {name} ...")
        n = 0
        try:
            async for _ in plugin.crawl():
                n += 1
        except Exception as e:
            print(f"  ! {name} failed: {e}", file=sys.stderr)
        print(f"  ✓ {name}: {n} repos")


def _cmd_serve(args):
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="info")


def _cmd_plugin_list(args):
    n = registry.discover()
    print(f"{n} plugins discovered:")
    for kind in ("source", "scorer", "notifier"):
        items = registry.list_by_kind(kind)
        if items:
            print(f"  [{kind}s]")
            for name, cls in items:
                print(f"    {name} v{getattr(cls, 'version', '?')}")


async def _cmd_migrate(args):
    url = os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/ai_radar")
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    import db as lodestone_db
    lodestone_db.ensure_database(database=db_name)
    lodestone_db.ensure_schema(database=db_name)
    conn = await asyncpg.connect(url)
    try:
        await migrate_mod.migrate(Store(conn))
    finally:
        await conn.close()
    print("migration complete")


def main():
    p = argparse.ArgumentParser(prog="lodestone", description=f"Lodestone {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("crawl").add_argument("--source")
    s_serve = sub.add_parser("serve")
    s_serve.add_argument("--port", type=int, default=8765)
    sub.add_parser("plugin-list")
    sub.add_parser("migrate")
    args = p.parse_args()
    if args.cmd == "crawl":
        asyncio.run(_cmd_crawl(args))
    elif args.cmd == "serve":
        _cmd_serve(args)
    elif args.cmd == "plugin-list":
        _cmd_plugin_list(args)
    elif args.cmd == "migrate":
        asyncio.run(_cmd_migrate(args))


if __name__ == "__main__":
    main()
