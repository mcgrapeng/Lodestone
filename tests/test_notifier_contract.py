"""Tests for lodestone.notifier base class contract.
Run: python3 -m tests.test_notifier_contract"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.notifier import Notifier, Notification


def test_notifier_is_abstract():
    assert inspect.isabstract(Notifier)


def test_notification_required_fields():
    n = Notification(kind="new_repo", title="x", body="y", repo_name="o/r", severity="info")
    assert n.kind == "new_repo"


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
