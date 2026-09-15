"""HuggingFace data source — fetches trending Spaces + Models."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import AsyncIterator
from lodestone.source import Source, SourceResult

log = logging.getLogger(__name__)


class HuggingFaceSource(Source):
    name = "huggingface"
    version = "2.0.0"
    config_schema = {
        "type": "object",
        "properties": {
            "spaces_endpoint": {"type": "string",
                                 "default": "https://huggingface.co/api/spaces?sort=trending"},
            "models_endpoint": {"type": "string",
                                 "default": "https://huggingface.co/api/models?sort=trending"},
            "include_spaces": {"type": "boolean", "default": True},
            "include_models": {"type": "boolean", "default": True},
        },
    }

    async def crawl(self) -> AsyncIterator[SourceResult]:
        if self.config.get("include_spaces", True):
            try:
                raw = await self._hf_api(self.config.get(
                    "spaces_endpoint", "https://huggingface.co/api/spaces?sort=trending"))
                for item in json.loads(raw):
                    yield SourceResult(
                        name=f"spaces/{item['id']}",
                        url=f"https://huggingface.co/spaces/{item['id']}",
                        description=None,
                        stars=item.get("likes", 0), forks=0,
                        lang=None, topics=[],
                        source_meta={"hf_kind": "space", "hf_id": item["id"]},
                    )
            except Exception as e:
                log.error("HF spaces crawl failed: %s", e)
        if self.config.get("include_models", True):
            try:
                raw = await self._hf_api(self.config.get(
                    "models_endpoint", "https://huggingface.co/api/models?sort=trending"))
                for item in json.loads(raw):
                    yield SourceResult(
                        name=f"models/{item['id']}",
                        url=f"https://huggingface.co/{item['id']}",
                        description=None,
                        stars=item.get("downloads", 0),
                        forks=item.get("likes", 0),
                        lang=None, topics=[],
                        source_meta={"hf_kind": "model", "hf_id": item["id"]},
                    )
            except Exception as e:
                log.error("HF models crawl failed: %s", e)

    async def _hf_api(self, url: str) -> str:
        proc = await asyncio.create_subprocess_shell(
            f"curl -sSf '{url}'", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"HF fetch failed: {url}")
        return stdout.decode()

    @property
    def config(self) -> dict:
        return getattr(self, "_config", {})
