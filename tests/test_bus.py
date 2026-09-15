"""Tests for lodestone.bus.PluginBus. Run: python3 -m tests.test_bus"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.bus import PluginBus


def test_subscribe_and_publish():
    bus = PluginBus()
    received = []
    def h(p): received.append(p)
    bus.subscribe("test.event", h)
    asyncio.run(bus.publish("test.event", {"x": 1}))
    assert received == [{"x": 1}]


def test_multiple_subscribers():
    bus = PluginBus()
    a, b = [], []
    bus.subscribe("e", lambda p: a.append(p))
    bus.subscribe("e", lambda p: b.append(p))
    asyncio.run(bus.publish("e", 1))
    assert a == [1] and b == [1]


def test_no_subscribers_is_noop():
    bus = PluginBus()
    asyncio.run(bus.publish("nothing", "x"))


def test_subscriber_error_does_not_break_others():
    bus = PluginBus()
    results = []
    def bad(p): raise ValueError("oops")
    def good(p): results.append(p)
    bus.subscribe("e", bad)
    bus.subscribe("e", good)
    asyncio.run(bus.publish("e", 42))
    assert results == [42]


def test_unsubscribe():
    bus = PluginBus()
    received = []
    h = lambda p: received.append(p)
    bus.subscribe("e", h)
    bus.unsubscribe("e", h)
    asyncio.run(bus.publish("e", 1))
    assert received == []


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
