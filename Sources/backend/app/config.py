"""Infrastructure settings: database URLs, model names, the Ollama address.

Read from environment variables or `backend/.env`. Users do not change these in the UI.
The RAG settings users CAN change (Top K, temperature, chunk size, …) are hyperparameters
of the registered methods in app/rag/registry.py.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic import field_validator
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
    if name.startswith("HYU/snapshots/"):
        snapshot_name = name.split("/", 2)[-1]
        folder = (root / "HYU" / "snapshots" / snapshot_name).resolve()
        return folder if folder.is_relative_to(root) and folder.is_dir() else None
    folder = (root / name).resolve()
    return folder if folder.is_relative_to(root) and folder.is_dir() else None


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
    trace_ttl_days: int = Field(default=30, ge=0)
    clean_reply: bool = True  # deck v7: remove internal markers, merge "ask the office" cases (app only; runs score the raw text)
    followup_resolution: bool = True  # deck v6: a detail-only reply to an AAES question answers the earlier question (app only)
    # The HYU snapshot index revision that HYU experiments, labeling and the demo use (PLAYBOOK A13).
    # r1/r2 stay in the databases for rollback; switch back with HYU_INDEX_ID=hyu_20261110_97dc1269_r2.
    hyu_index_id: str = "hyu_20261110_97dc1269_r5"

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
    groq_api_keys: str = Field(
        default="",
        validation_alias=AliasChoices("GROQ_API_KEYS", "groq_api_keys"),
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("GROQ_BASE_URL", "groq_base_url"),
    )
    groq_chat_model: str = Field(
        default="qwen/qwen3.8-27b",
        validation_alias=AliasChoices("GROQ_CHAT_MODEL", "groq_chat_model"),
    )
    groq_chat_models: str = Field(
        default="qwen/qwen3.8-27b,llama-3.1-8b-instant,openai/gpt-oss-20b,llama-3.3-70b-versatile",
        validation_alias=AliasChoices("GROQ_CHAT_MODELS", "groq_chat_models"),
    )

    # Ollama (legacy/local provider)
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "ollama_base_url"),
    )
    ollama_chat_model: str = Field(
        default="",
        validation_alias=AliasChoices("OLLAMA_CHAT_MODEL", "ollama_chat_model"),
    )
    ollama_timeout: float = 120.0

    data_dir: Path = DATA_DIR
    cors_origins: list[str] = Field(
        default=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "https://calm-ground-0036c6b00.4.azurestaticapps.net",
        ],
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    @field_validator("mongodb_uri", mode="before")
    @classmethod
    def ignore_empty_mongodb_uri(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return "mongodb://127.0.0.1:27017"
        return value

    @field_validator("qdrant_url", mode="before")
    @classmethod
    def ignore_empty_qdrant_url(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return "http://127.0.0.1:6333"
        return value

    @field_validator("mongodb_db", mode="before")
    @classmethod
    def ignore_empty_database_name(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return "hyu_compass"
        return value

    @field_validator("qdrant_api_key", "groq_api_key", mode="before")
    @classmethod
    def empty_secret_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ["http://127.0.0.1:5173", "http://localhost:5173"]
            if text.startswith("["):
                import json
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
