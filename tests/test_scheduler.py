"""Tests for lodestone.scheduler. Run: python3 -m tests.test_scheduler"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock

from lodestone.scheduler import Scheduler


def test_scheduler_add_and_inspect():
    sch = Scheduler()
    fn = AsyncMock()
    sch.add_cron("test", "* * * * *", fn)
    assert "test" in sch._jobs
    assert sch._jobs["test"]["expr"] == "* * * * *"


def test_scheduler_manual_run_calls_action():
    sch = Scheduler()
    fn = AsyncMock()
    sch.add_cron("t", "* * * * *", fn)

    async def run():
        await sch.run_now("t")
        fn.assert_awaited_once()

    asyncio.run(run())


def test_scheduler_run_now_unknown_raises():
    sch = Scheduler()

    async def run():
        try:
            await sch.run_now("nope")
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError")

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
