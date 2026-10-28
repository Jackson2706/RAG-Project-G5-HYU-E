"""Health and Ollama status endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import State
from app.services.ollama import OllamaError

router = APIRouter(tags=["system"])


async def _check(fn) -> dict[str, Any]:
    try:
        await asyncio.to_thread(fn)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": f"{exc.__class__.__name__}: {str(exc)[:200]}"}


@router.get("/health", summary="Connectivity of MongoDB, Qdrant and Ollama plus the active index")
async def health(state: State) -> dict[str, Any]:
    s = state.services
    mongo, qdrant = await asyncio.gather(_check(s.mongo.ping), _check(s.qdrant.ping))
    qdrant["mode"] = "local (exact search)" if s.qdrant.local_mode else "server"
    try:
        ollama = {"ok": True, "version": await s.ollama.version()}
    except OllamaError as exc:
        ollama = {"ok": False, "error": str(exc)}
    active = None
    if mongo["ok"]:
        revision = await s.active_revision()
        if revision:
            active = {"revision_id": revision.revision_id, "collection": revision.collection_name, "doc_count": revision.doc_count,
                      "chunk_count": revision.chunk_count, "embedding_model": revision.embedding.model_id,
                      "dimension": revision.embedding.dimension, "activated_at": revision.activated_at}  # fmt: skip
    return {"status": "ok" if mongo["ok"] and qdrant["ok"] and ollama["ok"] else "degraded",
            "mongodb": mongo, "qdrant": qdrant, "ollama": ollama, "active_index": active}  # fmt: skip


@router.get("/ollama/status", summary="Ollama reachability and configured default model")
async def ollama_status(state: State) -> dict[str, Any]:
    s = state.services
    out: dict[str, Any] = {"base_url": s.ollama.base_url, "configured_model": state.settings.ollama_chat_model or None}
    try:
        out["version"] = await s.ollama.version()
        models = await s.ollama.list_models()
        out.update(reachable=True, model_count=len(models))
        if not models:
            out["hint"] = "No models installed. Run `ollama pull <model>`, e.g. `ollama pull qwen3:4b`."
    except OllamaError as exc:
        out.update(reachable=False, error=str(exc), hint="Start Ollama with `ollama serve` (or open the Ollama app).")
    return out


@router.get("/ollama/models", summary="Installed Ollama models (from /api/tags)")
async def ollama_models(state: State) -> dict[str, Any]:
    try:
        models = await state.services.ollama.list_models()
    except OllamaError as exc:
        raise HTTPException(503, str(exc)) from exc
    default = state.settings.ollama_chat_model if state.settings.ollama_chat_model in {m["name"] for m in models} else None
    return {"models": models, "default": default or (models[0]["name"] if models else None)}


@router.get("/ollama/show", summary="Model details (from /api/show)")
async def ollama_show(state: State, model: str = Query(min_length=1, max_length=200)) -> dict[str, Any]:
    try:
        return await state.services.ollama.show(model)
    except OllamaError as exc:
        raise HTTPException(404 if exc.kind == "model_not_found" else 503, str(exc)) from exc

