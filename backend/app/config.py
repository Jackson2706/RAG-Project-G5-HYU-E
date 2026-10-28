"""Infrastructure settings: database URLs, model names, the Ollama address.

Read from environment variables or `backend/.env`. Users do not change these in the UI.
The RAG settings users CAN change (Top K, temperature, chunk size, …) are hyperparameters
of the registered methods in app/rag/registry.py.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Databases (started with `docker compose up -d`)
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "hyu_compass"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_path: str | None = None  # optional: embedded Qdrant in a folder instead of the Docker server
    qdrant_collection: str = "hyu_chunks"

    # Embedding model (must be the same for documents and questions)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str | None = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    # BGE expects this prefix on search questions (not on documents).
    query_instruction: str = "Represent this sentence for searching relevant passages: "

    # Ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = ""  # empty = first installed model
    ollama_timeout: float = 120.0

    data_dir: Path = PROJECT_ROOT / "data"
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
