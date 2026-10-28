"""Typed contracts for one online RAG execution: context, candidates, traces, events, API I/O."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.config import PipelineConfig, ResolvedConfig
from app.models.documents import SourceSpan

StageStatus = Literal["pending", "running", "completed", "bypassed", "failed"]
PipelineStatus = Literal["running", "completed", "failed", "cancelled"]
EventType = Literal[
    "pipeline_started",
    "stage_started",
    "stage_completed",
    "stage_bypassed",
    "stage_failed",
    "answer_delta",
    "answer_completed",
    "pipeline_completed",
    "pipeline_error",
]


class Candidate(BaseModel):
    """A retrieved chunk as it moves through retrieval → fusion → enrichment → selection.

    Scores from different retrievers are kept in separate fields because they are
    not on comparable scales (cosine similarity vs. BM25 vs. RRF).
    """

    chunk_id: str
    doc_id: str
    version_id: str | None = None
    dense_score: float | None = None
    dense_rank: int | None = None
    lexical_score: float | None = None
    lexical_rank: int | None = None
    fused_score: float | None = None
    fused_rank: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict, description="Compact Qdrant/filter payload.")
    # Filled by metadata enrichment (MongoDB lookup)
    text: str | None = None
    token_count: int | None = None
    title: str | None = None
    source_uri: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_number: int | None = None
    page_end: int | None = None
    source_span: SourceSpan | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryUnderstanding(BaseModel):
    language: str = "en"
    detected_constraints: dict[str, Any] = Field(default_factory=dict)
    matched_rules: list[str] = Field(default_factory=list)


class MetadataFilterSpec(BaseModel):
    """Validated metadata constraints. Compiled to a Qdrant filter and to an in-memory predicate."""

    campus: str | None = None
    audience: list[str] = Field(default_factory=list)
    document_type: str | None = None
    academic_year: str | None = None
    language: str | None = None
    include_unknown: bool = True
    include_university_wide: bool = True

    def is_empty(self) -> bool:
        return not (self.campus or self.audience or self.document_type or self.academic_year or self.language)


class SufficiencyDecision(BaseModel):
    sufficient: bool
    reason: str
    checks: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    marker: str = Field(description="Label used in the prompt and answer, e.g. 'S1'.")
    chunk_id: str
    doc_id: str
    title: str | None = None
    source_uri: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_number: int | None = None
    source_span: SourceSpan | None = None
    excerpt: str = ""
    cited: bool = Field(default=False, description="The answer references this marker.")
    resolved: bool = Field(default=False, description="Chunk and document exist in MongoDB.")
    span_verified: bool | None = Field(default=None, description="Stored span reproduces the chunk text.")


class CitationReport(BaseModel):
    method: str
    cited_markers: list[str] = Field(default_factory=list)
    invalid_markers: list[str] = Field(default_factory=list, description="Markers that match no evidence.")
    uncited_evidence: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    span_failures: list[str] = Field(default_factory=list)
    sentences_total: int = 0
    sentences_with_citation: int = 0
    note: str = "Checks citation identity and span resolution only; it does not verify that claims are true."


class AnswerResult(BaseModel):
    answer: str
    outcome: Literal["answered", "insufficient_evidence", "abstained", "failed"]
    citations: list[Citation] = Field(default_factory=list)
    citation_report: CitationReport | None = None
    guard_notes: list[str] = Field(default_factory=list)
    model: str | None = None


class PipelineContext(BaseModel):
    """Shared, typed state carried through the online stages."""

    request_id: str
    session_id: str | None = None
    question: str = Field(description="Original user question (never modified).")
    query: str = Field(description="Query text used for retrieval (after rewriting).")
    understanding: QueryUnderstanding = Field(default_factory=QueryUnderstanding)
    rewritten_queries: list[str] = Field(default_factory=list)
    filter_spec: MetadataFilterSpec | None = None
    dense_candidates: list[Candidate] = Field(default_factory=list)
    lexical_candidates: list[Candidate] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list, description="Current fused/reranked candidate list.")
    evidence: list[Candidate] = Field(default_factory=list, description="Selected evidence passed to generation.")
    sufficiency: SufficiencyDecision | None = None
    context_text: str = ""
    messages: list[dict[str, str]] = Field(default_factory=list, description="Chat messages sent to the LLM.")
    raw_answer: str = ""
    model: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    citation_report: CitationReport | None = None
    result: AnswerResult | None = None
    index_revision: dict[str, Any] = Field(default_factory=dict)


class StageTrace(BaseModel):
    request_id: str
    stage_id: str
    stage_name: str
    method_id: str | None
    status: StageStatus
    implementation_status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    summary: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    bypass_reason: str | None = None


class ExecutionTrace(BaseModel):
    request_id: str
    session_id: str | None = None
    created_at: datetime
    question: str
    status: PipelineStatus
    config: ResolvedConfig
    index_revision: dict[str, Any] = Field(default_factory=dict)
    stages: list[StageTrace] = Field(default_factory=list)
    result: AnswerResult | None = None
    total_ms: float | None = None
    error: str | None = None


class PipelineEvent(BaseModel):
    """One SSE event. `stage` is set for stage_* events, `delta` for answer_delta."""

    type: EventType
    request_id: str
    timestamp: datetime
    stage: StageTrace | None = None
    delta: str | None = None
    result: AnswerResult | None = None
    trace: ExecutionTrace | None = None
    error: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)
    config: PipelineConfig = Field(default_factory=PipelineConfig)


class ChatResponse(BaseModel):
    request_id: str
    result: AnswerResult | None
    trace: ExecutionTrace
