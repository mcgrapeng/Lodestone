"""PluginBus — async pub/sub for plugin events. Subscriber errors are isolated."""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Awaitable, Callable, Union

log = logging.getLogger(__name__)
SyncHandler = Callable[[Any], None]
AsyncHandler = Callable[[Any], Awaitable[None]]
Handler = Union[SyncHandler, AsyncHandler]


class PluginBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}

    def subscribe(self, event: str, handler: Handler) -> None:
        self._subs.setdefault(event, []).append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        if event in self._subs:
            try:
                self._subs[event].remove(handler)
            except ValueError:
                pass

    async def publish(self, event: str, payload: Any) -> None:
        for handler in list(self._subs.get(event, [])):
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                log.warning("subscriber for %s raised", event, exc_info=True)


bus = PluginBus()
