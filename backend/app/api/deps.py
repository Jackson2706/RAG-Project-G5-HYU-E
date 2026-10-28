"""Application state shared by the routers (injected with FastAPI's Depends)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.ingestion.pipeline import IngestionPipeline
from app.rag.pipeline import RAGPipeline, RAGServices


@dataclass
class AppState:
    settings: Settings
    services: RAGServices
    pipeline: RAGPipeline
    ingestion: IngestionPipeline


def get_state(request: Request) -> AppState:
    return request.app.state.hyu


State = Annotated[AppState, Depends(get_state)]
