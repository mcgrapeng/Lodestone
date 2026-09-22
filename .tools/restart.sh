#!/usr/bin/env bash
# Restart both lodestone servers (radar backend + vite dev frontend).
# Usage: bash .tools/restart.sh
#
# Idempotent: kills existing PIDs on :8765 / :5174 first, then starts fresh.
# Pure bash — no Python dependency, no setsid (which macOS doesn't ship).
# Detach trick: nohup + & + disown + /dev/null stdin so the bash subshell
# that runs my tooling can't kill children via SIGHUP.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$ROOT/data/logs"
mkdir -p "$LOGDIR"

echo "→ killing existing servers (if any)…"
lsof -ti:8765 -ti:5174 2>/dev/null | sort -u | xargs -r kill 2>/dev/null || true
sleep 1

echo "→ starting radar.py serve (port 8765)…"
cd "$ROOT"
nohup ./.venv/bin/python radar.py serve --port 8765 \
  >"$LOGDIR/serve.log" 2>"$LOGDIR/serve.err" </dev/null &
RADAR_PID=$!
disown $RADAR_PID 2>/dev/null || true

echo "→ starting vite dev server (port 5174)…"
cd "$ROOT/frontend"
nohup node node_modules/vite/bin/vite.js --port 5174 --force \
  >"$LOGDIR/vite.log" 2>"$LOGDIR/vite.err" </dev/null &
VITE_PID=$!
disown $VITE_PID 2>/dev/null || true

# Give them a beat to bind sockets
sleep 3

echo
echo "┌─ result ─────────────────────────────────────────────"
echo "│ radar: PID $RADAR_PID  port 8765"
echo "│ vite:  PID $VITE_PID   port 5174"
echo "│"
HEALTH=$(curl -sS --max-time 3 http://127.0.0.1:8765/api/health 2>&1 || echo "down")
VITE=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:5174/ 2>&1 || echo "down")
echo "│ radar /api/health: $HEALTH"
echo "│ vite / status:     HTTP $VITE"
echo "└─────────────────────────────────────────────────────"
echo
echo "Open: http://127.0.0.1:5174/"
echo "Logs: $LOGDIR/serve.log  $LOGDIR/vite.log"