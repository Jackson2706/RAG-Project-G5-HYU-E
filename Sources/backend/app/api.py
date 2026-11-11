"""All HTTP endpoints. Interactive docs: http://127.0.0.1:8000/docs"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings, resolve_ingest_folder
from app.database import DEFAULT_INDEX, Database
from app.ollama import OllamaError
from app.rag.pipeline import run_ingestion, run_rag
from app.rag.presets import presets_json
from app.rag.registry import PIPELINE, ConfigError, registry_json, validate_config
from app.rag.schemas import Services

router = APIRouter(prefix="/api")

StageChoices = dict[str, dict[str, Any]]  # {stage_id: {"method": "...", "params": {...}}}


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    stages: StageChoices = Field(default_factory=dict, description="Methods and parameters per stage; missing stages use defaults")
    index_id: str = Field(default=DEFAULT_INDEX, description="Which index revision to search (GET /api/indexes)")
    history: list[str] = Field(default_factory=list, max_length=20, description="Earlier user turns of this session (AAES step 1)")


class IngestRequest(BaseModel):
    folder: str = Field(default="HYU/raw", description="Folder relative to DATA_DIR, e.g. 'HYU/raw', or 'sample_data' for the sample documents")
    stages: StageChoices = Field(default_factory=dict, description="Offline methods and parameters (e.g. chunk size)")


def services(request: Request, index_id: str = DEFAULT_INDEX) -> Services:
    return Services(db=index_database(request, index_id), ollama=request.app.state.ollama, settings=get_settings())


def index_database(request: Request, index_id: str) -> Database:
    try:
        return request.app.state.db.for_index(index_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


async def check_runnable(request: Request, config: dict, index_id: str) -> None:
    """Problems that need the running services: the index must exist and match the embedding method,
    and every selected Ollama model must be installed. Raises HTTP 422 before anything runs."""
    errors = []
    db = index_database(request, index_id)
    manifest = db.get_manifest()
    if index_id != DEFAULT_INDEX and manifest is None:
        errors.append({"stage_id": None, "param": None, "message": f"Index '{index_id}' does not exist"})
    # older indexes have no manifest: each document still records its embedding method
    built_with = ((manifest or {}).get("embedding_contract") or {}).get("method") or db.index_info()["embedding_method"]
    if built_with and built_with != config["embedding"]["method"]:
        errors.append({"stage_id": "embedding", "param": None, "message": f"Index '{index_id}' was built with the '{built_with}' embedding; "
                       f"select it (vectors of different models cannot be compared)"})  # fmt: skip
    tagged = [s.stage_id for s in PIPELINE if config[s.stage_id]["method"] in ("applicability_reranker", "applicability_sufficiency")]
    if tagged and not (manifest or {}).get("applicability"):
        errors.append({"stage_id": tagged[0], "param": None, "message": f"Index '{index_id}' has no applicability tags. AAES needs the "
                       f"tagged HYU index ('{get_settings().hyu_index_id}')."})  # fmt: skip
    wanted = {(s.stage_id, name, config[s.stage_id]["params"][name]) for s in PIPELINE for m in s.methods
              if config[s.stage_id]["method"] == m.method_id for name, p in m.parameters.items()
              if p.ui == "ollama_model" and config[s.stage_id]["params"].get(name)}  # fmt: skip
    if wanted:
        try:
            installed = {m["name"] for m in await request.app.state.ollama.list_models()}
        except OllamaError as exc:
            installed = None
            errors.append({"stage_id": None, "param": None, "message": str(exc)})
        for stage_id, name, model in sorted(wanted):
            if installed is not None and model not in installed:
                errors.append({"stage_id": stage_id, "param": name, "message": f"Ollama model '{model}' is not installed. Run: ollama pull {model}"})
    if errors:
        raise HTTPException(422, {"message": "This configuration cannot run", "errors": errors})


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


@router.get("/pipeline/presets")
async def pipeline_presets():
    """Named experiment configurations (B0, O0–O8, R0–R14), each validated with the registry — from app/rag/presets.py."""
    return {"presets": presets_json()}


@router.get("/indexes")
async def indexes(request: Request, include_smoke: bool = False):
    """The app's index plus every benchmark index revision, with the manifest describing how it was built.
    Indexes of smoke runs (small corpus slices) are left out unless include_smoke=true."""
    found = []
    for entry in request.app.state.db.list_index_revisions():
        if not include_smoke and ((entry["manifest"] or {}).get("corpus") or {}).get("smoke_slice"):
            continue
        db = request.app.state.db.for_index(entry["index_id"])
        found.append({**entry, "info": db.index_info()})
    return {"indexes": found, "default": DEFAULT_INDEX}


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
    """Re-ingest DATA_DIR/<folder> with the offline methods in `stages`. Replaces the whole index."""
    config = checked(body.stages)
    folder = resolve_ingest_folder(body.folder, get_settings().data_dir)
    if folder is None or not folder.is_dir():
        raise HTTPException(400, f"'{body.folder}' is not a folder under the configured data directory")
    try:
        return await asyncio.to_thread(run_ingestion, folder, config, services(request))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, str(exc)) from exc


# ------------------------------------------------------------------------- chat


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """Answer a question and return the complete trace (no streaming)."""
    config = checked(body.stages)
    await check_runnable(request, config, body.index_id)
    return await run_rag(body.question.strip(), config, services(request, body.index_id), history=body.history)


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request):
    """Answer a question as Server-Sent Events: started → stage … → answer_delta … → done."""
    config = checked(body.stages)  # invalid settings fail here, before anything runs
    await check_runnable(request, config, body.index_id)
    run_services = services(request, body.index_id)
    queue: asyncio.Queue = asyncio.Queue()

    async def run():
        try:
            await run_rag(body.question.strip(), config, run_services, emit=queue.put_nowait, history=body.history)
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
