"""StarsScorer — log-scaled star count → 0-1 score."""
from __future__ import annotations
import math
from lodestone.scorer import Scorer, Score


class StarsScorer(Scorer):
    name = "stars"
    version = "2.0.0"
    config_schema = {
        "type": "object",
        "properties": {
            "log_base": {"type": "integer", "default": 100,
                          "description": "Stars for score 0.5 (log midpoint)"},
            "max_score_at": {"type": "integer", "default": 10000,
                                "description": "Stars at which score saturates at 1.0"},
        },
    }

    async def score(self, repo: dict, context: dict) -> Score:
        stars = int(repo.get("stars", 0))
        if stars <= 0:
            return Score(value=0.0, reasoning="no stars")
        midpoint = int(self.config.get("log_base", 100))
        cap = int(self.config.get("max_score_at", 10000))
        ratio = math.log(stars) / math.log(cap)
        value = min(1.0, max(0.0, ratio))
        return Score(value=value, reasoning=f"stars={stars} → {value:.2f}")

    @property
    def config(self) -> dict:
        return getattr(self, "_config", {})
