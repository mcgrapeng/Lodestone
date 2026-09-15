"""Webhook notifier — POST notification to user-configured URL."""
from __future__ import annotations
import asyncio
import json
import logging
import urllib.error
import urllib.request
from lodestone.notifier import Notifier, Notification

log = logging.getLogger(__name__)


class WebhookNotifier(Notifier):
    name = "webhook"
    version = "2.0.0"
    config_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "format": "uri"},
            "timeout_seconds": {"type": "integer", "default": 5},
        },
        "required": ["url"],
    }

    async def notify(self, notification: Notification) -> None:
        url = self.config.get("url")
        if not url:
            log.warning("webhook notifier has no URL configured; dropping %s", notification.kind)
            return
        body = json.dumps({
            "kind": notification.kind, "title": notification.title,
            "body": notification.body, "repo_name": notification.repo_name,
            "severity": notification.severity,
        }).encode()
        req = urllib.request.Request(url, data=body,
                                       headers={"Content-Type": "application/json"}, method="POST")
        timeout = int(self.config.get("timeout_seconds", 5))
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=timeout))
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            log.warning("webhook POST %s failed: %s", url, e)

    @property
    def config(self) -> dict:
        return getattr(self, "_config", {})
