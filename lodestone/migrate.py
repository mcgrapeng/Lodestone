"""1.x → 2.0 data migration. Run: python3 -m lodestone.migrate (or via T14 CLI)."""
from __future__ import annotations
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


async def migrate(store) -> None:
    """Reads 1.x's data/latest.json + data/settings.json into 2.0 store."""
    latest = Path("data/latest.json")
    if latest.exists():
        data = json.loads(latest.read_text())
        from lodestone.source import SourceResult
        repo_count = 0
        for entry in data.get("repos", []):
            r = SourceResult(
                name=entry["name"], url=entry["url"],
                description=entry.get("description"),
                stars=entry.get("stars", 0), forks=entry.get("forks", 0),
                lang=entry.get("lang"),
                topics=entry.get("topics", []),
                source_meta={"1.x_import": True},
            )
            await store.upsert_repo(r, source_name="1.x_migration")
            repo_count += 1
        for entry in data.get("categories", []):
            cid = entry["id"]
            for r2 in entry.get("repos", []):
                await store.conn.execute("""
                    INSERT INTO repo_categories (repo_name, category_id, score)
                    VALUES ($1, $2, 1.0) ON CONFLICT DO NOTHING
                """, r2["name"], cid)
        log.info("migrated %d repos from data/latest.json", repo_count)

    settings = Path("data/settings.json")
    if settings.exists():
        s = json.loads(settings.read_text())
        for k, v in s.items():
            await store.set_setting(k, v)
        log.info("migrated %d settings from data/settings.json", len(s))

    log.info("migration complete")
