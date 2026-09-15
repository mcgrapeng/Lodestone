"""arXiv source — fetches recent AI papers via the arXiv Atom API."""
from __future__ import annotations
import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import AsyncIterator
from urllib.parse import urlencode
from lodestone.source import Source, SourceResult

log = logging.getLogger(__name__)
NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivSource(Source):
    name = "arxiv"
    version = "2.0.0"
    config_schema = {
        "type": "object",
        "properties": {
            "categories": {"type": "array", "items": {"type": "string"},
                            "default": ["cs.AI", "cs.CL", "cs.LG"]},
            "max_results": {"type": "integer", "default": 30},
        },
    }

    async def crawl(self) -> AsyncIterator[SourceResult]:
        cats = self.config.get("categories", ["cs.AI", "cs.CL", "cs.LG"])
        max_results = int(self.config.get("max_results", 30))
        params = urlencode({
            "search_query": " OR ".join(f"cat:{c}" for c in cats),
            "start": 0, "max_results": max_results,
            "sortBy": "submittedDate", "sortOrder": "descending",
        })
        url = f"http://export.arxiv.org/api/query?{params}"
        try:
            raw = await self._fetch(url)
            root = ET.fromstring(raw)
        except Exception as e:
            log.error("arXiv crawl failed: %s", e)
            return
        for entry in root.findall("atom:entry", NS):
            arxiv_id = entry.findtext("atom:id", default="", namespaces=NS)
            arxiv_id = arxiv_id.rsplit("/", 1)[-1] if arxiv_id else ""
            yield SourceResult(
                name=f"arxiv/{arxiv_id}",
                url=f"https://arxiv.org/abs/{arxiv_id}",
                description=entry.findtext("atom:summary", default="", namespaces=NS).strip(),
                stars=0, forks=0, lang="TeX",
                topics=cats,
                source_meta={"arxiv_id": arxiv_id,
                          "title": entry.findtext("atom:title", default="", namespaces=NS)},
            )

    async def _fetch(self, url: str) -> str:
        proc = await asyncio.create_subprocess_shell(
            f"curl -sSf '{url}'", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"arXiv fetch failed: {url}")
        return stdout.decode()

    @property
    def config(self) -> dict:
        return getattr(self, "_config", {})
