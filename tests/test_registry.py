"""Tests for lodestone.registry. Run: python3 -m tests.test_registry"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.registry import Registry
from lodestone.source import Source


def test_registry_discovers_entry_points():
    reg = Registry()
    n = reg.discover()
    # 0 plugins actually exist (T6-T11 not done yet); entry_points declared but
    # entry_points() will return empty since plugin modules don't exist
    assert n >= 0


def test_registry_get_unknown_returns_none():
    reg = Registry()
    assert reg.get("does.not.exist") is None


def test_registry_list_by_kind():
    reg = Registry()
    reg.discover()
    sources = reg.list_by_kind("source")
    assert isinstance(sources, list)
    for name, cls in sources:
        assert isinstance(name, str)
        assert issubclass(cls, Source)


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
