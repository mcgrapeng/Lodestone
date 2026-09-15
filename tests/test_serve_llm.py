"""Tests for /api/llm/* endpoints (2026-09 P3 拆分). Run: python3 -m tests.test_serve_llm"""
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

os.environ.setdefault("no_proxy", "*")

from radar_pkg import core


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _get(url: str, timeout: float = 5) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read() or b"{}"
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw.decode("utf-8", errors="replace")[:200]}


def _post(url: str, body: dict | None = None, timeout: float = 5) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read() or b"{}"
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw.decode("utf-8", errors="replace")[:200]}


def _spawn_serve(port: int) -> subprocess.Popen:
    project_root = Path(__file__).parent.parent
    return subprocess.Popen(
        [sys.executable, str(project_root / "radar.py"), "serve", str(port)],
        cwd=str(project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def _wait_health(port: int, timeout_s: float = 8) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        try:
            status, _ = _get(f"http://127.0.0.1:{port}/api/health", timeout=1)
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def _setup_settings(payload: dict | None) -> None:
    """Write settings.json. None = delete file."""
    if payload is None:
        core.SETTINGS_PATH.unlink(missing_ok=True)
    else:
        core.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        core.SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1))


def test_llm_status_unconfigured():
    """No settings file → provider default but configured=false (api_key empty)."""
    port = _free_port()
    _setup_settings(None)
    proc = _spawn_serve(port)
    try:
        assert _wait_health(port), "serve didn't come up"
        status, body = _get(f"http://127.0.0.1:{port}/api/llm/status")
        assert status == 200, body
        assert body["configured"] is False, body
        assert "provider" in body
        assert "running" in body
        assert body["running"] is False
        print(f"  unconfigured status: provider={body['provider']}, configured={body['configured']}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_llm_status_ollama_configured():
    """Ollama with host set → configured=true."""
    port = _free_port()
    _setup_settings({
        "provider": "ollama",
        "ollama": {"host": "http://127.0.0.1:11434", "model": "qwen2.5:3b"},
    })
    proc = _spawn_serve(port)
    try:
        assert _wait_health(port), "serve didn't come up"
        status, body = _get(f"http://127.0.0.1:{port}/api/llm/status")
        assert status == 200, body
        assert body["configured"] is True, body
        assert body["provider"] == "ollama", body
        print(f"  ollama status: configured=True, provider={body['provider']}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_llm_status_openai_empty_key_not_configured():
    """OpenAI provider selected but api_key empty → configured=false."""
    port = _free_port()
    _setup_settings({
        "provider": "openai",
        "openai": {"base_url": "https://api.openai.com/v1", "api_key": "", "model": "gpt-4o-mini"},
    })
    proc = _spawn_serve(port)
    try:
        assert _wait_health(port), "serve didn't come up"
        status, body = _get(f"http://127.0.0.1:{port}/api/llm/status")
        assert status == 200, body
        assert body["configured"] is False, body
        assert body["provider"] == "openai", body
        print(f"  openai-empty: configured=False despite provider=openai")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_llm_summarize_rejects_unconfigured():
    """POST /api/llm/summarize with no api_key → 400."""
    port = _free_port()
    _setup_settings(None)
    proc = _spawn_serve(port)
    try:
        assert _wait_health(port), "serve didn't come up"
        status, body = _post(f"http://127.0.0.1:{port}/api/llm/summarize", {})
        assert status == 400, (status, body)
        assert "no LLM provider configured" in body.get("error", ""), body
        print(f"  unconfigured POST: 400 with msg")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_llm_summarize_ollama_spawns():
    """POST /api/llm/summarize with ollama → 200, summarize.lock created briefly."""
    port = _free_port()
    _setup_settings({
        "provider": "ollama",
        "ollama": {"host": "http://127.0.0.1:11434", "model": "qwen2.5:3b"},
    })
    # 清掉旧 lock/status — 防止上一次跑残留下次进不去
    core.SUMMARIZE_LOCK.unlink(missing_ok=True)
    core.LLM_STATUS_PATH.unlink(missing_ok=True)
    # 造一个空 latest.json + README cache,使 summarize 跑得快(empty repos → 0 analyzed)
    latest_path = core.DATA / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps({
        "date": "2026-09-15", "fetched_at": "2026-09-15T12:00:00",
        "total_unique": 0, "hot_now": [], "categories": [],
    }))
    readme_path = core.README_ZH_CACHE
    readme_path.write_text(json.dumps({}))
    proc = _spawn_serve(port)
    try:
        assert _wait_health(port), "serve didn't come up"
        status, body = _post(f"http://127.0.0.1:{port}/api/llm/summarize", {})
        assert status == 200, (status, body)
        assert body.get("ok") is True, body
        assert body.get("provider") == "ollama", body
        # Wait for subprocess to finish (no README → should be near-instant)
        for _ in range(20):
            time.sleep(0.2)
            if not core.SUMMARIZE_LOCK.exists():
                break
        assert not core.SUMMARIZE_LOCK.exists(), "summarize.lock stuck after 4s"
        # status file written
        assert core.LLM_STATUS_PATH.exists(), "llm_status.json not written"
        status_data = json.loads(core.LLM_STATUS_PATH.read_text())
        assert status_data["provider"] == "ollama", status_data
        assert status_data["analyzed"] == 0, status_data
        print(f"  ollama POST: 200 → spawned subprocess → lock released → status written")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        # cleanup test residue
        core.SUMMARIZE_LOCK.unlink(missing_ok=True)
        latest_path.unlink(missing_ok=True)
        readme_path.unlink(missing_ok=True)


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
