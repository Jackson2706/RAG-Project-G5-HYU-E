"""Schemas for the method/hyperparameter registry and for pipeline configurations.

The registry (app/rag/registry.py) is built from these classes and served to the
frontend, which renders controls from it. Validation lives here so that the same
rules are applied to every request and never duplicated in the UI.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ImplementationStatus(StrEnum):
    implemented = "implemented"
    planned = "planned"
    unavailable = "unavailable"


class ParamType(StrEnum):
    integer = "integer"
    float = "float"
    boolean = "boolean"
    enum = "enum"
    string = "string"
    string_list = "string_list"  # free-form list of strings (e.g. stop sequences)
    multi_enum = "multi_enum"  # subset of `options`


class Control(StrEnum):
    slider = "slider"
    number = "number"
    toggle = "toggle"
    select = "select"
    text = "text"
    textarea = "textarea"
    tags = "tags"
    multiselect = "multiselect"
    ollama_model = "ollama_model"  # select populated from installed Ollama models


class Scope(StrEnum):
    runtime = "runtime"  # may change per question
    ingestion = "ingestion"  # requires re-running ingestion (re-chunk / re-parse)
    index = "index"  # changes vector compatibility; requires a new index revision


class Option(BaseModel):
    value: Any
    label: str


class ParameterSpec(BaseModel):
    name: str
    label: str
    type: ParamType
    default: Any
    description: str
    control: Control
    scope: Scope = Scope.runtime
    level: Literal["basic", "advanced"] = "basic"
    nullable: bool = False
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str | None = None
    options: list[Option] | None = None
    visible_when: dict[str, list[Any]] | None = Field(
        default=None, description="Show only when every named sibling parameter has one of the listed values."
    )

    def validate_value(self, value: Any) -> Any:
        """Coerce and validate one value. Raises ValueError with a user-facing message."""
        if value is None:
            if self.nullable:
                return None
            raise ValueError(f"{self.label} is required")
        t = self.type
        if t is ParamType.boolean:
            if not isinstance(value, bool):
                raise ValueError(f"{self.label} must be true or false")
            return value
        if t in (ParamType.integer, ParamType.float):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{self.label} must be a number")
            if t is ParamType.integer:
                if float(value) != int(value):
                    raise ValueError(f"{self.label} must be an integer")
                value = int(value)
            else:
                value = float(value)
            if self.min is not None and value < self.min:
                raise ValueError(f"{self.label} must be ≥ {self.min:g}")
            if self.max is not None and value > self.max:
                raise ValueError(f"{self.label} must be ≤ {self.max:g}")
            return value
        if t is ParamType.string:
            if not isinstance(value, str):
                raise ValueError(f"{self.label} must be text")
            return value
        allowed = {o.value for o in self.options or []}
        if t is ParamType.enum:
            if value not in allowed:
                raise ValueError(f"{self.label}: '{value}' is not one of {sorted(map(str, allowed))}")
            return value
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"{self.label} must be a list of strings")
        if t is ParamType.multi_enum:
            unknown = [v for v in value if v not in allowed]
            if unknown:
                raise ValueError(f"{self.label}: unknown value(s) {unknown}")
        return list(dict.fromkeys(value))


class MethodSpec(BaseModel):
    method_id: str
    display_name: str
    description: str
    status: ImplementationStatus
    implementation: str | None = Field(default=None, description="Python reference of the implementation.")
    parameters: list[ParameterSpec] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list, description="Human-readable compatibility notes.")


class StageSpec(BaseModel):
    stage_id: str
    stage_name: str
    description: str
    category: Literal["offline", "online"]
    can_disable: bool = False
    enabled: bool = Field(default=True, description="Default enabled state.")
    selected_method: str = Field(description="Default method.")
    available_methods: list[MethodSpec]
    reads: list[str] = Field(default_factory=list, description="Pipeline context fields consumed.")
    writes: list[str] = Field(default_factory=list, description="Pipeline context fields produced.")
    dependencies: list[str] = Field(default_factory=list)
    requires_reindexing: bool = False

    @property
    def implementation_status(self) -> ImplementationStatus:
        statuses = {m.status for m in self.available_methods}
        return ImplementationStatus.implemented if ImplementationStatus.implemented in statuses else min(statuses)

    def method(self, method_id: str) -> MethodSpec | None:
        return next((m for m in self.available_methods if m.method_id == method_id), None)


class StageConfig(BaseModel):
    enabled: bool | None = None
    method: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """A (possibly partial) configuration draft: stage_id -> settings. Missing values take defaults."""

    stages: dict[str, StageConfig] = Field(default_factory=dict)


class ResolvedStageConfig(BaseModel):
    model_config = {"frozen": True}

    enabled: bool
    method: str
    params: dict[str, Any]


class ResolvedConfig(BaseModel):
    """A complete, validated, immutable configuration snapshot used for exactly one execution."""

    model_config = {"frozen": True}

    stages: dict[str, ResolvedStageConfig]
    config_hash: str

    def stage(self, stage_id: str) -> ResolvedStageConfig:
        return self.stages[stage_id]


class ValidationIssue(BaseModel):
    stage_id: str | None = None
    param: str | None = None
    message: str


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    resolved: ResolvedConfig | None = None


class Preset(BaseModel):
    preset_id: str
    name: str
    description: str
    builtin: bool = False
    config: PipelineConfig
    available: bool = True
    unavailable_reason: str | None = None
