"""Tests for lodestone.scorer base class contract.
Run: python3 -m tests.test_scorer_contract"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.scorer import Scorer, Score


def test_score_required_fields():
    s = Score(value=0.8, reasoning="fresh")
    assert s.value == 0.8


def test_scorer_subclass_must_implement_score():
    class BadScorer(Scorer):
        name = "bad"
        version = "0"
        config_schema = {}
    try:
        BadScorer()
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
