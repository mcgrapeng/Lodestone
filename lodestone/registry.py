"""Plugin registry — discovers entry_points, instantiates plugins."""
from __future__ import annotations
import logging
from importlib.metadata import entry_points
from typing import Type

log = logging.getLogger(__name__)


class Registry:
    def __init__(self) -> None:
        self._plugins: dict[str, Type] = {}

    def discover(self) -> int:
        self._plugins.clear()
        for group in ("lodestone.sources", "lodestone.scorers", "lodestone.notifiers"):
            try:
                eps = entry_points(group=group)
            except Exception as e:
                log.warning("failed to load entry_points group %s: %s", group, e)
                continue
            for ep in eps:
                try:
                    cls = ep.load()
                except Exception as e:
                    log.warning("plugin %s failed to load: %s — disabling", ep.name, e)
                    continue
                self._plugins[ep.name] = cls
        log.info("discovered %d plugins: %s", len(self._plugins), list(self._plugins))
        return len(self._plugins)

    def get(self, name: str):
        cls = self._plugins.get(name)
        return cls() if cls is not None else None

    def list_by_kind(self, kind: str) -> list[tuple[str, type]]:
        out = []
        try:
            for ep in entry_points(group=f"lodestone.{kind}s"):
                if ep.name in self._plugins:
                    out.append((ep.name, self._plugins[ep.name]))
        except Exception as e:
            log.warning("list_by_kind(%s) failed: %s", kind, e)
        return out


registry = Registry()
