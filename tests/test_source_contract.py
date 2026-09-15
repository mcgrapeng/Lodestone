"""Tests for lodestone.source base class contract.
Run: python3 -m tests.test_source_contract"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.source import Source, SourceResult


def test_source_is_abstract():
    assert inspect.isabstract(Source)


def test_source_result_required_fields():
    r = SourceResult(
        name="o/r", url="https://github.com/o/r", description="x",
        stars=10, forks=1, lang="Python", topics=[], source_meta={},
    )
    assert r.name == "o/r"
    assert r.stars == 10


def test_source_subclass_must_implement_crawl():
    class BadSource(Source):
        name = "bad"
        version = "0"
        config_schema = {}
    try:
        BadSource()
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
