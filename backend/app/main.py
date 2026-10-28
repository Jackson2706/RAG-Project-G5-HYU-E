"""Starts the FastAPI app and connects MongoDB, Qdrant and Ollama.

Run from the backend/ folder (Conda env `RAG`):   python -m uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings
from app.database import Database
from app.ollama import OllamaClient

log = logging.getLogger("hyu_compass")


def create_app(db: Database | None = None, ollama: OllamaClient | None = None) -> FastAPI:
    """Build the app. Tests pass their own `db` and `ollama`; normally both are created from settings."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db = db or Database.connect(settings)
        app.state.ollama = ollama or OllamaClient(settings.ollama_base_url, settings.ollama_timeout)
        try:
            app.state.db.create_indexes()
        except Exception as exc:  # the API still starts; /api/health shows what is wrong
            log.error("MongoDB is not reachable (%s). Start it with: docker compose up -d", exc)
        yield
        await app.state.ollama.http.aclose()

    app = FastAPI(title="HYU Compass API", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    return app


logging.basicConfig(level=logging.INFO)
app = create_app()
