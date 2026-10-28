"""Shared setup for the CLI scripts: import path, Conda check, repository connections."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

if os.environ.get("CONDA_DEFAULT_ENV") != "RAG" and "/envs/RAG/" not in sys.executable:
    print(f"warning: not running in the Conda environment 'RAG' (python: {sys.executable})", file=sys.stderr)

from app.config import BACKEND_DIR, get_settings  # noqa: E402
from app.repositories.mongodb import MongoRepository  # noqa: E402
from app.repositories.qdrant import QdrantRepository  # noqa: E402


def connect() -> tuple[MongoRepository, QdrantRepository]:
    settings = get_settings()
    mongo = MongoRepository.connect(settings.mongodb_uri, settings.mongodb_db)
    try:
        mongo.ping()
    except Exception as exc:
        sys.exit(f"MongoDB is not reachable at {settings.mongodb_uri.split('@')[-1]}: {exc}\nStart it with `docker compose up -d`.")
    mongo.ensure_indexes()
    path = settings.qdrant_path
    if path and not Path(path).is_absolute():
        path = str((BACKEND_DIR / path).resolve())
    try:
        qdrant = QdrantRepository.connect(settings.qdrant_url, path, settings.qdrant_alias, settings.qdrant_api_key)
        qdrant.ping()
    except Exception as exc:
        hint = ("Local-mode Qdrant allows one process at a time: stop the API server or use POST /api/v1/ingest/local."
                if path else "Start it with `docker compose up -d`.")  # fmt: skip
        sys.exit(f"Qdrant is not reachable: {exc}\n{hint}")
    return mongo, qdrant
