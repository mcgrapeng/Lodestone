"""MCP Registry source — fetches the official Model Context Protocol server list."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import AsyncIterator
from urllib.parse import urlparse
from lodestone.source import Source, SourceResult

log = logging.getLogger(__name__)


class MCPRegistrySource(Source):
    name = "mcp_registry"
    version = "2.0.0"
    config_schema = {
        "type": "object",
        "properties": {
            "endpoint": {"type": "string",
                          "default": "https://registry.modelcontextprotocol.io/v0/servers"},
        },
    }

    async def crawl(self) -> AsyncIterator[SourceResult]:
        try:
            raw = await self._fetch(self.config.get(
                "endpoint", "https://registry.modelcontextprotocol.io/v0/servers"))
            data = json.loads(raw)
        except Exception as e:
            log.error("MCP registry fetch failed: %s", e)
            return
        for s in data.get("servers", []):
            repo_url = s.get("repoUrl", "")
            if "github.com" not in repo_url:
                continue
            path = urlparse(repo_url).path.strip("/")
            yield SourceResult(
                name=path.removesuffix(".git"),
                url=repo_url,
                description=s.get("description"),
                stars=s.get("stars", 0), forks=0,
                lang=s.get("language"),
                topics=s.get("tags", []),
                source_meta={"mcp_name": s.get("name")},
            )

    async def _fetch(self, url: str) -> str:
        proc = await asyncio.create_subprocess_shell(
            f"curl -sSf '{url}'", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"MCP fetch failed: {url}")
        return stdout.decode()

    @property
    def config(self) -> dict:
        return getattr(self, "_config", {})
