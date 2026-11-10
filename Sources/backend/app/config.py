"""Infrastructure settings: database URLs, model names, the Ollama address.

Read from environment variables or `backend/.env`. Users do not change these in the UI.
The RAG settings users CAN change (Top K, temperature, chunk size, …) are hyperparameters
of the registered methods in app/rag/registry.py.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
REPORT_DIR = Path(os.environ.get("HYU_REPORT_DIR", REPO_ROOT / "Report"))
DATA_DIR = Path(os.environ.get("HYU_DATA_DIR", PROJECT_ROOT / "data"))  # Sources/data (PLAYBOOK A12)
RESULTS_DIR = Path(os.environ.get("HYU_RESULTS_DIR", REPORT_DIR / "results"))
SAMPLE_DATA_DIR = BACKEND_DIR / "sample_data"  # 5 invented practice documents for the app's default index
SAMPLE_FOLDER = "sample_data"  # the folder name ingest/API/UI use for it


def resolve_ingest_folder(name: str, data_dir: Path | None = None) -> Path | None:
    """"sample_data" → SAMPLE_DATA_DIR; any other name → a folder under the data directory; None if it escapes it."""
    if name == SAMPLE_FOLDER:
        return SAMPLE_DATA_DIR
    root = (data_dir or DATA_DIR).resolve()
    folder = (root / name).resolve()
    return folder if folder.is_relative_to(root) else None


def resolve_stored_path(path: str | Path) -> Path:
    """Resolve paths stored before data and results moved under Report."""
    path = Path(path)
    if path.is_absolute():
        return path
    if path.parts[:1] == ("data",):
        return DATA_DIR.joinpath(*path.parts[1:])
    if path.parts[:1] == ("results",):
        return RESULTS_DIR.joinpath(*path.parts[1:])
    return REPO_ROOT / path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Databases (started with `docker compose up -d`)
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "hyu_compass"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_path: str | None = None  # optional: embedded Qdrant in a folder instead of the Docker server
    qdrant_collection: str = "hyu_chunks"
    # The HYU snapshot index revision that HYU experiments, labeling and the demo use (PLAYBOOK A13).
    # r1/r2 stay in the databases for rollback; switch back with HYU_INDEX_ID=hyu_20261110_97dc1269_r2.
    hyu_index_id: str = "hyu_20261110_97dc1269_r3"

    # Embedding model (must be the same for documents and questions)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str | None = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    # BGE expects this prefix on search questions (not on documents).
    query_instruction: str = "Represent this sentence for searching relevant passages: "
    # "cpu", "mps" (Apple GPU) or "auto" (= mps when available). The app uses cpu; the benchmark runner uses auto.
    embedding_device: str = "cpu"

    # Ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = ""  # empty = first installed model
    ollama_timeout: float = 120.0

    data_dir: Path = DATA_DIR
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
