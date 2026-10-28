"""Centralized application settings, loaded from environment variables / backend/.env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "hyu_compass"

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_path: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection_prefix: str = "hyu_chunks"

    embedding_model_id: str = "BAAI/bge-small-en-v1.5"
    embedding_model_revision: str | None = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    embedding_device: str = "cpu"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = ""
    ollama_request_timeout: float = 120.0

    data_dir: Path = PROJECT_ROOT / "data"
    max_upload_mb: int = 20
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    # Bounds applied to every stage input/output stored in traces or streamed over SSE.
    trace_max_string: int = 4000
    trace_max_items: int = 50

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def qdrant_alias(self) -> str:
        """Alias that always points at the published (verified) collection."""
        return f"{self.qdrant_collection_prefix}_active"


@lru_cache
def get_settings() -> Settings:
    return Settings()
