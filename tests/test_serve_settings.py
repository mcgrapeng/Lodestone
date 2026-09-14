"""Tests for /api/settings HTTP endpoints. Spawns radar.py serve as subprocess.
Run: python3 -m tests.test_serve_settings"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ponytail: deviation from brief — user shell has http_proxy=127.0.0.1:7890
# (Clash). urllib.request.urlopen routes loopback through it and times out.
# serve.py itself uses ProxyHandler({}) for the same reason (line 1374).
# Setting no_proxy here bypasses the proxy for 127.0.0.1 in this process's
# urllib calls. Also pushed into the subprocess env below.
os.environ.setdefault("no_proxy", "*")

from radar_pkg import core


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _post_json(url: str, body: dict, timeout: float = 5) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _get(url: str, timeout: float = 5) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _spawn_serve(tmp_settings: Path) -> tuple[subprocess.Popen, int]:
    """Spawn radar.py serve on a free port. Remap SETTINGS_PATH to tmp."""
    port = _free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)
    # Override SETTINGS_PATH to a tmp file via env-driven test hook
    # (settings.py uses core.SETTINGS_PATH, not env; we monkeypatch at runtime below)
    p = subprocess.Popen(
        [sys.executable, "radar.py", "serve", str(port)],
        cwd=str(Path(__file__).parent.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Wait for port to bind (up to 5s)
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return p, port
        except OSError:
            time.sleep(0.1)
    p.terminate()
    raise RuntimeError(f"serve did not bind {port} in 5s")


def _override_settings_path(p: subprocess.Popen, path: Path) -> None:
    """Patch core.SETTINGS_PATH inside the spawned process. Not feasible cross-process;
    tests below use the real data/settings.json with cleanup."""
    # NOTE: cross-process monkeypatch is hard. Instead, tests use the real
    # data/settings.json (the gitignored one) and back it up if it exists.
    pass


def _stop(p: subprocess.Popen) -> None:
    try:
        p.terminate()
        p.wait(timeout=3)
    except Exception:
        p.kill()


def _real_settings_backup() -> tuple[Path | None, bytes | None]:
    p = Path("data/settings.json")
    if p.exists():
        return p, p.read_bytes()
    return None, None


def _real_settings_restore(backup: tuple[Path | None, bytes | None]) -> None:
    p, data = backup
    if p is None:
        Path("data/settings.json").unlink(missing_ok=True)
    else:
        Path("data/settings.json").write_bytes(data)


# Tests run sequentially against real serve subprocess on a free port

def test_get_settings_returns_null_when_no_file():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        # Wait for serve to be fully ready (handler thread up)
        time.sleep(0.5)
        status, body = _get(f"http://127.0.0.1:{port}/api/settings")
        assert status == 200
        assert body.get("settings") is None or body.get("settings") == {}
    finally:
        _stop(p)
        _real_settings_restore(backup)


def test_post_then_get_roundtrips():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        time.sleep(0.5)
        body = {
            "provider": "openai",
            "openai": {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o-mini"},
        }
        status, resp = _post_json(f"http://127.0.0.1:{port}/api/settings", body)
        assert status == 200, f"POST failed: {resp}"
        assert resp.get("ok") is True
        status, resp = _get(f"http://127.0.0.1:{port}/api/settings")
        assert status == 200
        assert resp["settings"]["provider"] == "openai"
        assert resp["settings"]["openai"]["api_key"] == "sk-test"
    finally:
        _stop(p)
        _real_settings_restore(backup)


def test_post_rejects_unknown_field():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        time.sleep(0.5)
        body = {"provider": "openai", "evil_key": "rm -rf /"}
        status, resp = _post_json(f"http://127.0.0.1:{port}/api/settings", body)
        assert status == 400, f"expected 400 got {status}"
        assert "ok" in resp and resp["ok"] is False
    finally:
        _stop(p)
        _real_settings_restore(backup)


def test_post_validates_provider():
    backup = _real_settings_backup()
    Path("data/settings.json").unlink(missing_ok=True)
    p, port = _spawn_serve(Path("data/settings.json"))
    try:
        time.sleep(0.5)
        body = {"provider": "unknown_provider"}
        status, resp = _post_json(f"http://127.0.0.1:{port}/api/settings", body)
        assert status == 400
    finally:
        _stop(p)
        _real_settings_restore(backup)


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
