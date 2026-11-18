"""Infrastructure settings: database URLs, model names, the Ollama address.

Read from environment variables or `backend/.env`. Users do not change these in the UI.
The RAG settings users CAN change (Top K, temperature, chunk size, …) are hyperparameters
of the registered methods in app/rag/registry.py.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[BACKEND_DIR / ".env", PROJECT_ROOT / ".env"], extra="ignore")

    # Databases (started with `docker compose up -d`)
    mongodb_uri: str = Field(
        default="mongodb://127.0.0.1:27017",
        validation_alias=AliasChoices("MONGODB_URI", "MONGO_URI"),
    )
    mongodb_db: str = Field(
        default="hyu_compass",
        validation_alias=AliasChoices("MONGODB_DB", "MONGO_DB"),
    )
    qdrant_url: str = Field(
        default="http://127.0.0.1:6333",
        validation_alias=AliasChoices("QDRANT_URL"),
    )
    qdrant_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("QDRANT_API_KEY"),
    )
    qdrant_path: str | None = None  # optional: embedded Qdrant in a folder instead of the Docker server
    qdrant_collection: str = Field(
        default="hyu_chunks",
        validation_alias=AliasChoices("QDRANT_COLLECTION", "qdrant_collection"),
    )

    # Embedding model (must be the same for documents and questions)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str | None = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    # BGE expects this prefix on search questions (not on documents).
    query_instruction: str = "Represent this sentence for searching relevant passages: "
    # "cpu", "mps" (Apple GPU) or "auto" (= mps when available). The app uses cpu; the benchmark runner uses auto.
    embedding_device: str = "cpu"

    # LLM provider
    llm_provider: str = Field(
        default="ollama",
        validation_alias=AliasChoices("LLM_PROVIDER", "llm_provider"),
    )
    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "groq_api_key"),
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("GROQ_BASE_URL", "groq_base_url"),
    )
    groq_chat_model: str = Field(
        default="",
        validation_alias=AliasChoices("GROQ_CHAT_MODEL", "groq_chat_model"),
    )

    # Ollama (legacy/local provider)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = ""  # empty = first installed model
    ollama_timeout: float = 120.0

    data_dir: Path = PROJECT_ROOT / "data"
    cors_origins: list[str] = Field(
        default=["http://127.0.0.1:5173", "http://localhost:5173"],
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
