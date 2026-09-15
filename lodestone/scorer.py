"""Scorer plugin base — assigns 0-1 score to a repo for ranking."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Score:
    value: float
    reasoning: str = ""


@dataclass
class ScoredRepo:
    repo_name: str
    category_id: str
    score: "Score"


class Scorer(ABC):
    name: str = ""
    version: str = "0.0.0"
    config_schema: dict = {}

    @abstractmethod
    async def score(self, repo: dict, context: dict) -> Score:
        raise NotImplementedError
