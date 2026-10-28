"""All HTTP endpoints. Interactive docs: http://127.0.0.1:8000/docs"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.ollama import OllamaError
from app.rag.pipeline import run_ingestion, run_rag
from app.rag.registry import ConfigError, registry_json, validate_config
from app.rag.schemas import Services

router = APIRouter(prefix="/api")

StageChoices = dict[str, dict[str, Any]]  # {stage_id: {"method": "...", "params": {...}}}


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    stages: StageChoices = Field(default_factory=dict, description="Methods and parameters per stage; missing stages use defaults")


class IngestRequest(BaseModel):
    folder: str = Field(default="raw", description="Folder inside data/, e.g. 'raw' or 'samples'")
    stages: StageChoices = Field(default_factory=dict, description="Offline methods and parameters (e.g. chunk size)")


def services(request: Request) -> Services:
    return Services(db=request.app.state.db, ollama=request.app.state.ollama, settings=get_settings())


def checked(stages: StageChoices) -> dict:
    """Validate a configuration with the registry; invalid → HTTP 422 with the list of problems."""
    try:
        return validate_config(stages)
    except ConfigError as exc:
        raise HTTPException(422, {"message": "Invalid pipeline configuration", "errors": exc.errors}) from exc


# ------------------------------------------------------------------------- status & registry


@router.get("/health")
async def health(request: Request):
    db = request.app.state.db
    status = db.check()
    try:
        status["ollama"] = {"ok": True, "models": len(await request.app.state.ollama.list_models())}
    except OllamaError as exc:
        status["ollama"] = {"ok": False, "error": str(exc)}
    status["index"] = db.index_info() if status["mongodb"]["ok"] and status["qdrant"]["ok"] else None
    return status


@router.get("/pipeline/registry")
async def pipeline_registry():
    """Every stage, its methods (implemented or not) and their hyperparameters — from app/rag/registry.py."""
    return registry_json()


@router.post("/pipeline/config/validate")
async def validate(stages: StageChoices):
    try:
        return {"valid": True, "config": validate_config(stages), "errors": []}
    except ConfigError as exc:
        return {"valid": False, "config": None, "errors": exc.errors}


@router.get("/ollama/models")
async def ollama_models(request: Request):
    try:
        models = await request.app.state.ollama.list_models()
    except OllamaError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"models": models, "default": get_settings().ollama_chat_model or (models[0]["name"] if models else None)}


# ------------------------------------------------------------------------- documents


@router.get("/documents")
async def documents(request: Request):
    return {"documents": request.app.state.db.list_documents(), "index": request.app.state.db.index_info()}


@router.post("/ingest")
async def ingest(body: IngestRequest, request: Request):
    """Re-ingest data/<folder> with the offline methods in `stages`. Replaces the whole index."""
    config = checked(body.stages)
    data_dir = get_settings().data_dir.resolve()
    folder = (data_dir / body.folder).resolve()
    if not folder.is_relative_to(data_dir) or not folder.is_dir():
        raise HTTPException(400, f"'{body.folder}' is not a folder inside data/")
    try:
        return await asyncio.to_thread(run_ingestion, folder, config, services(request))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, str(exc)) from exc


# ------------------------------------------------------------------------- chat


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """Answer a question and return the complete trace (no streaming)."""
    return await run_rag(body.question.strip(), checked(body.stages), services(request))


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request):
    """Answer a question as Server-Sent Events: started → stage … → answer_delta … → done."""
    config = checked(body.stages)  # invalid settings fail here, before anything runs
    queue: asyncio.Queue = asyncio.Queue()

    async def run():
        try:
            await run_rag(body.question.strip(), config, services(request), emit=queue.put_nowait)
        finally:
            queue.put_nowait(None)  # tells the stream below that we are finished

    async def events():
        task = asyncio.create_task(run())
        try:
            while (event := await queue.get()) is not None:
                yield f"data: {json.dumps(event, default=str)}\n\n"
        finally:
            if not task.done():  # the browser closed the connection: stop generating
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/traces/{request_id}")
async def get_trace(request_id: str, request: Request):
    trace = request.app.state.db.get_trace(request_id)
    if trace is None:
        raise HTTPException(404, "Trace not found")
    return trace
