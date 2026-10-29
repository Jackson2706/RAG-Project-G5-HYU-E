#!/usr/bin/env bash
# HYU Compass — one-time setup. Safe to run again: it never overwrites your .env files or your index.
#
#   ./setup.sh
#
# 1. checks the tools (Conda, Docker, Node.js, Ollama)
# 2. creates .env and backend/.env with a random MongoDB password (only if they do not exist)
# 3. installs the Python packages into the Conda environment `RAG` (creates it only if missing)
# 4. installs the frontend packages (npm ci)
# 5. starts MongoDB + Qdrant (docker compose) and downloads an Ollama model if none is installed
# 6. indexes data/samples, but only when the index is still empty
set -euo pipefail
cd "$(dirname "$0")"

ENV_NAME=RAG
PYTHON_VERSION=3.13
OLLAMA_MODEL=qwen3:4b

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# Docker Desktop on macOS does not always put `docker` on the PATH.
command -v docker >/dev/null || PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
# A script does not read your shell profile, so `conda` may be missing from the PATH: try the usual places.
command -v conda >/dev/null || for d in "${CONDA_EXE%/conda}" "$HOME"/miniconda3/bin "$HOME"/anaconda3/bin "$HOME"/miniforge3/bin /opt/homebrew/Caskroom/miniconda/base/bin; do
  [ -x "$d/conda" ] && PATH="$PATH:$d" && break
done

step "Checking tools"
command -v conda >/dev/null || die "Conda not found. Install Miniconda: https://docs.conda.io/en/latest/miniconda.html"
command -v docker >/dev/null || die "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
docker info >/dev/null 2>&1 || die "Docker is installed but not running. Start Docker Desktop and run ./setup.sh again."
command -v npm >/dev/null || die "Node.js not found. Install Node.js 20 or newer: https://nodejs.org/"
node_major=$(node -p 'process.versions.node.split(".")[0]')
[ "$node_major" -ge 20 ] || die "Node.js $node_major is too old; version 20 or newer is needed."
command -v ollama >/dev/null || warn "Ollama not found. Answers need it: https://ollama.com/download (setup continues)."
echo "conda, docker, node $(node --version) OK"

step "Environment files"
if [ ! -f .env ] && [ ! -f backend/.env ]; then
  password=$(openssl rand -hex 16)
  sed "s/^MONGO_ROOT_PASSWORD=.*/MONGO_ROOT_PASSWORD=$password/" .env.example > .env
  sed "s/change-me-locally/$password/" backend/.env.example > backend/.env
  echo "Created .env and backend/.env with a new random MongoDB password."
elif [ -f .env ] && [ -f backend/.env ]; then
  echo "Keeping the existing .env and backend/.env."
else
  die "Only one of .env and backend/.env exists. Both must hold the same MongoDB password; see .env.example and backend/.env.example."
fi
root_password=$(grep '^MONGO_ROOT_PASSWORD=' .env | cut -d= -f2-)
grep -q ":$root_password@" backend/.env || warn "The password in backend/.env (MONGODB_URI) does not match MONGO_ROOT_PASSWORD in .env."

step "Python packages (Conda environment '$ENV_NAME')"
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "Using the existing environment '$ENV_NAME'."
else
  conda create -y -n "$ENV_NAME" "python=$PYTHON_VERSION"
fi
conda run -n "$ENV_NAME" --no-capture-output python -m pip install -q -r backend/requirements.txt
echo "Python packages installed."

step "Frontend packages"
(cd frontend && npm ci --no-audit --no-fund)

step "Starting MongoDB and Qdrant"
docker compose up -d --wait

step "Ollama model"
if command -v ollama >/dev/null; then
  if ! ollama list >/dev/null 2>&1; then
    warn "Ollama is not running. Start the Ollama app, then run: ollama pull $OLLAMA_MODEL"
  elif [ "$(ollama list | tail -n +2 | wc -l)" -eq 0 ]; then
    ollama pull "$OLLAMA_MODEL"
  else
    echo "Models already installed:"; ollama list | tail -n +2 | awk '{print "  " $1}'
  fi
fi

step "Document index"
chunks=$(cd backend && conda run -n "$ENV_NAME" python -c \
  "from app.config import get_settings; from app.database import Database; print(Database.connect(get_settings()).chunks.count_documents({}))" 2>/dev/null | tail -1) || chunks=error
case "$chunks" in
  0) conda run -n "$ENV_NAME" --no-capture-output python scripts/ingest.py --path data/samples ;;
  error) warn "Could not read the index. Check the logs above, then run: conda run -n $ENV_NAME python scripts/ingest.py --path data/samples" ;;
  *) echo "Index already has $chunks chunks; not re-indexing. (To index your own files: conda run -n $ENV_NAME python scripts/ingest.py --path data/raw)" ;;
esac

step "Setup complete"
echo "Start the app with:  ./start.sh"
