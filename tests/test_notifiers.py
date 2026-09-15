"""Tests for the built-in notifiers. Run: python3 -m tests.test_notifiers"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.plugins.notifier_inapp import InappNotifier
from lodestone.plugins.notifier_webhook import WebhookNotifier
from lodestone.notifier import Notification


def test_inapp_inserts_via_store():
    notif = InappNotifier()
    store = MagicMock()
    store.insert_notification = AsyncMock()
    notif.bind_store(store)
    asyncio.run(notif.notify(Notification(
        kind="new_repo", title="t", body="b", repo_name="o/r", severity="info")))
    store.insert_notification.assert_awaited_once()
    assert store.insert_notification.call_args[0][0]["kind"] == "new_repo"


def test_webhook_no_url_is_noop():
    notif = WebhookNotifier()
    # No URL configured — should not raise
    asyncio.run(notif.notify(Notification(
        kind="new_repo", title="t", body="b", repo_name="o/r")))


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
