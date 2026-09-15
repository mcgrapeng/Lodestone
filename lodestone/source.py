"""Source plugin base — data sources yield repos during crawl."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class SourceResult:
    name: str
    url: str
    description: str | None
    stars: int
    forks: int
    lang: str | None
    topics: list[str] = field(default_factory=list)
    source_meta: dict[str, Any] = field(default_factory=dict)


class Source(ABC):
    name: str = ""
    version: str = "0.0.0"
    config_schema: dict = {}

    @abstractmethod
    async def crawl(self) -> AsyncIterator[SourceResult]:
        raise NotImplementedError
        yield  # type: ignore[unreachable]
