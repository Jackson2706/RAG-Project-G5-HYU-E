#!/usr/bin/env bash
# HYU Compass — start everything in the background.
#
#   ./start.sh
#
# Starts MongoDB + Qdrant (docker compose), the FastAPI backend (http://127.0.0.1:8000) and the
# React frontend (http://127.0.0.1:5173). Logs go to .run/backend.log and .run/frontend.log.
# Stop everything with ./stop.sh
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(pwd)

ENV_NAME=RAG
RUN_DIR="$ROOT/.run"
BACKEND_PORT=8000
FRONTEND_PORT=5173

step() { printf '\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null || PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
# A script does not read your shell profile, so `conda` may be missing from the PATH: try the usual places.
command -v conda >/dev/null || for d in "${CONDA_EXE%/conda}" "$HOME"/miniconda3/bin "$HOME"/anaconda3/bin "$HOME"/miniforge3/bin /opt/homebrew/Caskroom/miniconda/base/bin; do
  [ -x "$d/conda" ] && PATH="$PATH:$d" && break
done
command -v conda >/dev/null || die "Conda not found. Run ./setup.sh first."
[ -f .env ] && [ -f backend/.env ] && [ -d frontend/node_modules ] || die "Not set up yet. Run ./setup.sh first."
docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop and try again."
mkdir -p "$RUN_DIR"

port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
running() { [ -f "$RUN_DIR/$1.pid" ] && kill -0 "$(cat "$RUN_DIR/$1.pid")" 2>/dev/null; }

# wait_for NAME URL LOGFILE — poll until the URL answers (max 90 s)
wait_for() {
  for _ in $(seq 1 90); do
    curl -fs -o /dev/null "$2" && return 0
    running "$1" || { tail -20 "$3"; die "$1 stopped while starting. Full log: $3"; }
    sleep 1
  done
  die "$1 did not answer at $2 within 90 s. Log: $3"
}

step "MongoDB and Qdrant"
docker compose up -d --wait

ollama list >/dev/null 2>&1 || warn "Ollama is not running: questions cannot be answered until you start the Ollama app."

step "Backend  → http://127.0.0.1:$BACKEND_PORT"
if running backend; then
  echo "Already running (pid $(cat "$RUN_DIR/backend.pid"))."
elif port_busy "$BACKEND_PORT"; then
  die "Port $BACKEND_PORT is used by another program (see: lsof -iTCP:$BACKEND_PORT). Stop it and try again."
else
  (cd "$ROOT/backend" && exec nohup conda run -n "$ENV_NAME" --no-capture-output \
     python -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT") \
     > "$RUN_DIR/backend.log" 2>&1 < /dev/null &
  echo $! > "$RUN_DIR/backend.pid"
  wait_for backend "http://127.0.0.1:$BACKEND_PORT/api/health" "$RUN_DIR/backend.log"
fi

step "Frontend → http://127.0.0.1:$FRONTEND_PORT"
if running frontend; then
  echo "Already running (pid $(cat "$RUN_DIR/frontend.pid"))."
elif port_busy "$FRONTEND_PORT"; then
  die "Port $FRONTEND_PORT is used by another program (see: lsof -iTCP:$FRONTEND_PORT). Stop it and try again."
else
  (cd "$ROOT/frontend" && exec nohup npm run dev) > "$RUN_DIR/frontend.log" 2>&1 < /dev/null &
  echo $! > "$RUN_DIR/frontend.pid"
  wait_for frontend "http://127.0.0.1:$FRONTEND_PORT" "$RUN_DIR/frontend.log"
fi

printf '\n\033[1;32mHYU Compass is running:\033[0m open http://127.0.0.1:%s\n' "$FRONTEND_PORT"
echo "Logs: .run/backend.log, .run/frontend.log   ·   Stop: ./stop.sh"
