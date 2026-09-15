"""In-app notifier — INSERT into notifications table."""
from __future__ import annotations
import logging
from lodestone.notifier import Notifier, Notification

log = logging.getLogger(__name__)


class InappNotifier(Notifier):
    name = "in_app"
    version = "2.0.0"
    config_schema = {"type": "object", "properties": {}}

    def __init__(self) -> None:
        self._store = None

    def bind_store(self, store) -> None:
        self._store = store

    async def notify(self, notification: Notification) -> None:
        if self._store is None:
            log.warning("in-app notifier has no store bound; dropping %s", notification.kind)
            return
        await self._store.insert_notification({
            "kind": notification.kind, "title": notification.title,
            "body": notification.body, "repo_name": notification.repo_name,
            "severity": notification.severity,
        })
