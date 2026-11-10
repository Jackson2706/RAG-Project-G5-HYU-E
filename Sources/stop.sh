#!/usr/bin/env bash
# HYU Compass — stop what ./start.sh started. All data is kept.
#
#   ./stop.sh            # stop frontend, backend, MongoDB and Qdrant
#   ./stop.sh --keep-db  # stop frontend and backend only; databases keep running
set -euo pipefail
cd "$(dirname "$0")"

RUN_DIR=.run
KEEP_DB=false
case "${1:-}" in
  "") ;;
  --keep-db) KEEP_DB=true ;;
  *) echo "Usage: ./stop.sh [--keep-db]" >&2; exit 2 ;;
esac

step() { printf '\033[1;34m==> %s\033[0m\n' "$*"; }
command -v docker >/dev/null || PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"

# kill_tree PID — stop a process and everything it started (conda run → uvicorn → reload worker, npm → vite)
kill_tree() {
  local child
  for child in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$child"; done
  kill "$1" 2>/dev/null || true
}

for name in frontend backend; do
  step "Stopping $name"
  pidfile="$RUN_DIR/$name.pid"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    kill_tree "$(cat "$pidfile")"
    echo "Stopped (pid $(cat "$pidfile"))."
  else
    echo "Not running (or not started by ./start.sh)."
  fi
  rm -f "$pidfile"
done

if $KEEP_DB; then
  echo "MongoDB and Qdrant keep running (--keep-db)."
elif docker info >/dev/null 2>&1; then
  step "Stopping MongoDB and Qdrant (data is kept)"
  docker compose stop
else
  echo "Docker is not running, so the databases are already stopped."
fi
