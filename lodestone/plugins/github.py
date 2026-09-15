"""GitHub data source — uses `gh` CLI (1.x pattern) to avoid token management."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import AsyncIterator
from lodestone.source import Source, SourceResult

log = logging.getLogger(__name__)


class GitHubSource(Source):
    name = "github"
    version = "2.0.0"
    config_schema = {
        "type": "object",
        "properties": {
            "token": {"type": "string", "secret": True},
            "min_stars": {"type": "integer", "default": 50},
        },
    }

    async def crawl(self) -> AsyncIterator[SourceResult]:
        query = "topic:ai-agent stars:>50"
        try:
            raw = await self._gh_api("search/repositories",
                                     q=query, sort="stars", order="desc", per_page=30)
        except Exception as e:
            log.error("github crawl failed: %s", e)
            return
        data = json.loads(raw)
        for item in data.get("items", []):
            yield SourceResult(
                name=item["full_name"],
                url=item["html_url"],
                description=item.get("description"),
                stars=item.get("stargazers_count", 0),
                forks=item.get("forks_count", 0),
                lang=item.get("language"),
                topics=item.get("topics", []),
                source_meta={"github_id": item.get("id")},
            )

    async def _gh_api(self, endpoint: str, **params) -> str:
        cmd = ["gh", "api", endpoint]
        for k, v in params.items():
            cmd += ["-f", f"{k}={v}"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"gh api failed: {stderr.decode()}")
        return stdout.decode()

    @property
    def config(self) -> dict:
        return getattr(self, "_config", {})
