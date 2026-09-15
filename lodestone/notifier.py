"""Notifier plugin base — fans out events to user-configured channels."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Notification:
    kind: str
    title: str
    body: str = ""
    repo_name: str | None = None
    severity: str = "info"


class Notifier(ABC):
    name: str = ""
    version: str = "0.0.0"
    config_schema: dict = {}

    @abstractmethod
    async def notify(self, notification: Notification) -> None:
        raise NotImplementedError
