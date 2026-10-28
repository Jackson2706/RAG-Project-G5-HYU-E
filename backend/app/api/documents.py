"""Documents of the active index, index revisions, and ingestion triggers."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import AppState, State
from app.ingestion.loaders import MEDIA_TYPES
from app.models.config import PipelineConfig, StageConfig
from app.rag.registry import OFFLINE_ORDER, resolve_config

router = APIRouter(tags=["documents"])


async def _active(state: AppState):
    revision = await state.services.active_revision()
    if revision is None:
        raise HTTPException(404, "No active index. Ingest documents first.")
    return revision


@router.get("/documents", summary="Documents in the active index revision")
async def list_documents(state: State) -> dict[str, Any]:
    revision = await _active(state)
    docs = await asyncio.to_thread(state.services.mongo.get_documents, revision.doc_versions, False)
    items = [d.model_dump(exclude={"content"}) for d in sorted(docs.values(), key=lambda d: d.source_uri)]
    return {"revision_id": revision.revision_id, "documents": items}


@router.get("/documents/{doc_id}", summary="One document (active version) with its chunks")
async def get_document(doc_id: str, state: State, include_content: bool = False) -> dict[str, Any]:
    revision = await _active(state)
    version = revision.doc_versions.get(doc_id)
    if version is None:
        raise HTTPException(404, "Document is not part of the active index")
    mongo = state.services.mongo
    doc = await asyncio.to_thread(mongo.get_document, doc_id, version)
    if doc is None:
        raise HTTPException(404, "Document record missing")
    chunks = [c for c in await asyncio.to_thread(mongo.chunks_for_revision, revision.revision_id) if c.doc_id == doc_id]
    return {"document": doc.model_dump(exclude=None if include_content else {"content"}),
            "chunks": [c.model_dump(exclude={"index_revisions"}) for c in chunks]}  # fmt: skip


@router.get("/index", summary="Active index revision and revision history")
async def index_status(state: State) -> dict[str, Any]:
    revisions = await asyncio.to_thread(state.services.mongo.list_revisions)
    active_collection = await asyncio.to_thread(state.services.qdrant.active_collection)
    return {"active_alias": state.settings.qdrant_alias, "alias_target": active_collection,
            "revisions": [r.model_dump(mode="json", exclude={"offline_config"}) for r in revisions]}  # fmt: skip


class IngestLocalRequest(BaseModel):
    path: str = Field(default="raw", description="Directory or file relative to the data/ folder, e.g. 'raw' or 'samples'.")
    config: PipelineConfig = Field(default_factory=PipelineConfig, description="Offline-stage overrides; others use defaults.")
    activate: bool = True


def _safe_data_path(state: AppState, rel: str) -> Path:
    data_dir = state.settings.data_dir.resolve()
    target = (data_dir / rel).resolve()
    if not target.is_relative_to(data_dir):
        raise HTTPException(400, "Path must stay inside the data/ directory")
    if not target.exists():
        raise HTTPException(404, f"{rel} does not exist under data/")
    return target


async def _ingest(state: AppState, path: Path, draft: PipelineConfig, activate: bool) -> dict[str, Any]:
    result = resolve_config(draft, OFFLINE_ORDER)
    if not result.valid:
        raise HTTPException(422, {"message": "Invalid ingestion configuration", "errors": [e.model_dump() for e in result.errors]})
    try:
        report = await asyncio.to_thread(state.ingestion.run, path, result.resolved, activate)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return report.to_dict()


@router.post("/ingest/local", summary="Ingest files already under data/ into a new verified index revision")
async def ingest_local(body: IngestLocalRequest, state: State) -> dict[str, Any]:
    return await _ingest(state, _safe_data_path(state, body.path), body.config, body.activate)


SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@router.post("/ingest/files", summary="Upload documents into data/raw/uploads and optionally re-ingest data/raw")
async def ingest_files(state: State, files: list[UploadFile] = File(...), ingest: bool = Form(True)) -> dict[str, Any]:
    upload_dir = state.settings.raw_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    limit = state.settings.max_upload_mb * 1024 * 1024
    saved = []
    for f in files:
        name = SAFE_NAME.sub("_", Path(f.filename or "").name).strip("._")
        if not name or Path(name).suffix.lower() not in MEDIA_TYPES:
            raise HTTPException(415, f"Unsupported file '{f.filename}'. Allowed: {', '.join(sorted(MEDIA_TYPES))}")
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"'{f.filename}' exceeds {state.settings.max_upload_mb} MB")
        (upload_dir / name).write_bytes(data)
        saved.append(f"raw/uploads/{name}")
    report = None
    if ingest:
        revision = await state.services.active_revision()
        draft = PipelineConfig(stages={k: StageConfig(**v) for k, v in revision.offline_config.items()} if revision else {})
        report = await _ingest(state, state.settings.raw_dir, draft, True)
    return {"saved": saved, "ingestion": report}
