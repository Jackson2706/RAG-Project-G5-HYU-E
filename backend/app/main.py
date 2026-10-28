"""FastAPI application: wiring of repositories, services and routers.

Run (from backend/, Conda env `RAG`):  python -m uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents, pipeline, system
from app.api.deps import AppState
from app.config import BACKEND_DIR, Settings, get_settings
from app.ingestion.pipeline import IngestionPipeline
from app.rag.pipeline import RAGPipeline, RAGServices
from app.repositories.mongodb import MongoRepository
from app.repositories.qdrant import QdrantRepository
from app.services.ollama import OllamaClient

log = logging.getLogger("hyu_compass")


def build_state(settings: Settings) -> AppState:
    mongo = MongoRepository.connect(settings.mongodb_uri, settings.mongodb_db)
    try:
        mongo.ensure_indexes()
    except Exception as exc:  # the API still starts; /health reports the problem
        log.error("MongoDB is not reachable at startup (%s). Start it with `docker compose up -d`.", exc)
    qdrant_path = settings.qdrant_path
    if qdrant_path and not Path(qdrant_path).is_absolute():
        qdrant_path = str((BACKEND_DIR / qdrant_path).resolve())
    qdrant = QdrantRepository.connect(settings.qdrant_url, qdrant_path, settings.qdrant_alias, settings.qdrant_api_key)
    ollama = OllamaClient(settings.ollama_base_url, settings.ollama_request_timeout)
    services = RAGServices(settings, mongo, qdrant, ollama)
    return AppState(settings, services, RAGPipeline(services), IngestionPipeline(settings, mongo, qdrant))


def create_app(state: AppState | None = None) -> FastAPI:
    settings = state.settings if state else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.hyu = state or build_state(settings)
        yield
        await app.state.hyu.services.ollama.aclose()
        app.state.hyu.services.qdrant.client.close()

    app = FastAPI(title="HYU Compass API", version="0.1.0", lifespan=lifespan,
                  description="Evidence-aware RAG assistant and pipeline workbench for new Hanyang University students.")  # fmt: skip
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    for router in (system.router, pipeline.router, chat.router, documents.router):
        app.include_router(router, prefix="/api/v1")
    return app


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = create_app()
