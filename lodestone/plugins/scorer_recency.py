"""RecencyScorer — newer repos get higher score."""
from __future__ import annotations
from datetime import datetime, timezone
from lodestone.scorer import Scorer, Score


class RecencyScorer(Scorer):
    name = "recency"
    version = "2.0.0"
    config_schema = {
        "type": "object",
        "properties": {
            "decay_days": {"type": "integer", "default": 30,
                             "description": "Repos newer than this get 1.0; linear decay to 0.0"},
        },
    }

    async def score(self, repo: dict, context: dict) -> Score:
        decay = int(self.config.get("decay_days", 30))
        last_seen = repo.get("last_seen_at")
        if not last_seen:
            return Score(value=0.0, reasoning="no last_seen_at")
        if isinstance(last_seen, str):
            last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - last_seen).total_seconds() / 86400
        if age_days < 0:
            value = 1.0
        elif age_days >= decay:
            value = 0.0
        else:
            value = 1.0 - (age_days / decay)
        return Score(value=value, reasoning=f"age={age_days:.1f}d, decay={decay}d")

    @property
    def config(self) -> dict:
        return getattr(self, "_config", {})
