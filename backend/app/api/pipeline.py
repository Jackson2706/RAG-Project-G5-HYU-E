"""Registry, configuration validation and presets."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import State
from app.models.config import PipelineConfig, Preset, StageConfig, ValidationResult
from app.rag import registry

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/registry", summary="All stages, methods and hyperparameters (single source of truth for the UI)")
async def get_registry() -> dict[str, Any]:
    return registry.registry_payload()


@router.get("/config", summary="Default configuration and the offline configuration of the active index")
async def get_config(state: State) -> dict[str, Any]:
    defaults = registry.default_config()
    active = None
    try:
        revision = await state.services.active_revision()
    except Exception:
        revision = None
    if revision:
        active = revision.offline_config
        # Offline stages show the values the active index was actually built with.
        for stage_id in registry.OFFLINE_ORDER:
            if stage_id in active:
                defaults.stages[stage_id] = StageConfig(**active[stage_id])
    return {"config": defaults.model_dump(), "active_index_config": active}


@router.post("/config/validate", response_model=ValidationResult, summary="Validate a draft and return the resolved snapshot")
async def validate_config(draft: PipelineConfig, state: State) -> ValidationResult:
    result = registry.resolve_config(draft)
    if result.resolved:
        try:
            revision = await state.services.active_revision()
        except Exception:
            revision = None
        if revision:
            result.warnings += registry.offline_config_differences(result.resolved, revision.offline_config)
    return result


class PresetIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    config: PipelineConfig


@router.get("/presets", response_model=list[Preset])
async def list_presets(state: State) -> list[Preset]:
    presets = [registry.preset_availability(p) for p in registry.BUILTIN_PRESETS]
    try:
        saved = await asyncio.to_thread(state.services.mongo.list_presets)
    except Exception:
        saved = []
    return presets + [registry.preset_availability(Preset(**p)) for p in saved]


@router.post("/presets", response_model=Preset, status_code=201, summary="Save a validated configuration as a preset")
async def save_preset(body: PresetIn, state: State) -> Preset:
    result = registry.resolve_config(body.config)
    if not result.valid:
        raise HTTPException(422, {"message": "Configuration is invalid", "errors": [e.model_dump() for e in result.errors]})
    preset_id = "user_" + (re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_") or "preset")
    if preset_id.removeprefix("user_") in {p.preset_id for p in registry.BUILTIN_PRESETS}:
        raise HTTPException(409, "A built-in preset already uses this name")
    preset = Preset(preset_id=preset_id, name=body.name, description=body.description, config=body.config)
    await asyncio.to_thread(state.services.mongo.save_preset, preset.model_dump(mode="json"))
    return preset
