#!/usr/bin/env bash
# HYU Compass — remove what ./setup.sh installed.
#
#   ./uninstall.sh                 # stop everything; remove containers, node_modules, build output, caches, logs
#   ./uninstall.sh --delete-data   # ALSO delete the MongoDB + Qdrant volumes (index and traces). Asks first.
#
# Never removed: source code, documents in data/, your .env files, the Conda environment
# (shared with other course work), Ollama models and the Hugging Face model cache.
# The end of the script prints the commands to remove those yourself.
set -euo pipefail
cd "$(dirname "$0")"

DELETE_DATA=false
case "${1:-}" in
  "") ;;
  --delete-data) DELETE_DATA=true ;;
  *) echo "Usage: ./uninstall.sh [--delete-data]" >&2; exit 2 ;;
esac

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
command -v docker >/dev/null || PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"

if $DELETE_DATA; then
  printf '\033[1;31mThis permanently deletes the MongoDB and Qdrant data (indexed documents, chunks, traces).\033[0m\n'
  printf 'Your files in data/ are NOT deleted. Type "delete" to continue: '
  read -r answer
  [ "$answer" = "delete" ] || { echo "Cancelled. Nothing was changed."; exit 1; }
fi

step "Stopping the app"
./stop.sh --keep-db

step "Removing the database containers"
if docker info >/dev/null 2>&1; then
  if $DELETE_DATA; then
    docker compose down --volumes --remove-orphans
    echo "Containers and data volumes removed."
  else
    docker compose down --remove-orphans
    echo "Containers removed. Data volumes kept (hyu-compass_mongodb_data, hyu-compass_qdrant_data)."
  fi
else
  echo "Docker is not running; skipped. Start Docker Desktop and run ./uninstall.sh again to remove the containers."
fi

step "Removing installed and generated files"
rm -rf frontend/node_modules frontend/dist frontend/*.tsbuildinfo .run backend/.pytest_cache
find backend scripts -name __pycache__ -type d -prune -exec rm -rf {} +
echo "Removed frontend/node_modules, frontend/dist, .run/ and Python caches."

step "Done"
cat <<'EOF'
Kept on purpose — remove them yourself only if you are sure:
  .env, backend/.env                    rm .env backend/.env   (passwords; a kept data volume still needs the same password)
  Docker images                         docker image rm mongo:8.0.32 qdrant/qdrant:v1.19.0
  Ollama model                          ollama rm qwen3:4b
  Embedding model cache                 rm -rf ~/.cache/huggingface/hub/models--BAAI--bge-small-en-v1.5
  Conda environment (shared!)           conda env remove -n RAG

Reinstall any time with:  ./setup.sh
EOF
