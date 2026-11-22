"""The data that flows between pipeline blocks (Pydantic models).

Each block's `base.py` says which of these types it receives and returns, so you always know
what you get and what you must give back. Create them with keywords, e.g.
`Candidate(rank=1, chunk_id="…", doc_id="…", score=0.83)`.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # only for type hints; avoids import cycles
    from app.config import Settings
    from app.database import Database
    from app.ollama import OllamaClient
    from app.rag.blocks.ingestion.embedding.base import BaseEmbedder

# What the model writes when the evidence does not answer the question (see context_construction),
# and what the user then sees (abstention).
INSUFFICIENT_MARKER = "INSUFFICIENT_CONTEXT"
INSUFFICIENT_ANSWER = (
    "I could not find enough information in the indexed HYU documents to answer this question. "
    "Please check the official Hanyang University website or ask the relevant office."
)

# =========================================================================== ingestion (offline)


class Section(BaseModel):
    """A piece of a document under one heading (or one PDF page)."""

    heading: str | None
    text: str
    page: int | None = None


class ParsedDocument(BaseModel):
    """Output of parsing: the readable content of one file."""

    path: Path
    source_uri: str  # path relative to DATA_DIR, e.g. "HYU/raw/handbook.pdf"
    file_type: str  # "pdf" | "txt" | "md" | "html"
    title: str
    sections: list[Section]
    declared_metadata: dict[str, str] = Field(default_factory=dict)  # e.g. Markdown front matter

    def section_starts(self) -> list[int]:
        """Character position of each section inside `full_text()` (sections are joined by a blank line)."""
        starts, position = [], 0
        for section in self.sections:
            starts.append(position)
            position += len(section.text) + len(SECTION_SEPARATOR)
        return starts

    def full_text(self) -> str:
        """The whole document as one string. Chunk spans (`Chunk.start`, `Chunk.end`) point into it."""
        return SECTION_SEPARATOR.join(section.text for section in self.sections)


SECTION_SEPARATOR = "\n\n"


class DocumentMetadata(BaseModel):
    """Output of metadata extraction. Unknown values stay missing — never guessed."""

    title: str
    language: str
    extra: dict[str, str] = Field(default_factory=dict)


class Chunk(BaseModel):
    """Output of chunking: one searchable piece of a document.

    `start`/`end` is the chunk's source span: document.full_text()[start:end] == text.
    """

    text: str
    section: str | None
    page_number: int | None
    token_count: int
    start: int | None = None
    end: int | None = None


# =========================================================================== question answering (online)


class FilterCriteria(BaseModel):
    """Metadata conditions a student's question requires (eligibility). None = no condition.

    Only fill these from what the question or the student actually states — never invent them.
    """

    campus: str | None = None  # e.g. "SEOUL", "ERICA"
    audience: str | None = None  # e.g. "undergraduate", "international"
    academic_year: str | None = None  # e.g. "2026"
    document_type: str | None = None  # e.g. "handbook", "notice"
    effective_date: str | None = None  # e.g. "2026-03-01"

    def conditions(self) -> dict[str, str]:
        """Only the conditions that are set."""
        return {k: v for k, v in self.model_dump().items() if v not in (None, "")}

    def to_filter(self, include_unknown: bool = True, campus_wide_value: str | None = "all") -> RetrievalFilter | None:
        """The eligibility predicate for these criteria, or None when no condition is set.

        Prefiltering and Postfiltering both use this, so a placement comparison uses the SAME predicate.
        `campus_wide_value`: a document for every campus (campus: ALL) is also eligible for a campus.
        """
        conditions = {field: [normalize_value(value)] for field, value in self.conditions().items()}
        if not conditions:
            return None
        if "campus" in conditions and campus_wide_value:
            conditions["campus"].append(campus_wide_value)
        return RetrievalFilter(conditions=conditions, include_unknown=include_unknown)


def normalize_value(value: str) -> str:
    """Metadata values are compared case-insensitively ("ERICA" == "erica")."""
    return value.strip().lower()


def metadata_values(raw: Any) -> list[str]:
    """Declared metadata → list of normalized values. "[undergraduate, international]" → two values."""
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else str(raw).strip().strip("[]").split(",")
    return [normalize_value(str(item).strip().strip("'\"")) for item in items if str(item).strip().strip("'\"")]


class QueryAnalysis(BaseModel):
    """Output of query understanding: what the question asks for."""

    intent: str | None = None
    criteria: FilterCriteria = Field(default_factory=FilterCriteria)
    profile: dict[str, Any] = Field(default_factory=dict)  # AAES step 1: {attribute: {values, status, evidence}}


class RewrittenQuery(BaseModel):
    """Output of query rewriting. `query` is used for retrieval; the original question is kept for the prompt.

    alternatives:   extra search queries (multi-query); retrieval runs once per query and the
                    rankings are merged with Reciprocal Rank Fusion.
    embedding_text: a text to embed INSTEAD of the query for dense retrieval (HyDE). It is a search
                    representation only: never evidence, never cited.
    validation:     what the rewrite check found (passed, missing terms, fallback reason).
    """

    query: str
    alternatives: list[str] = Field(default_factory=list)
    embedding_text: str | None = None
    validation: dict[str, Any] = Field(default_factory=dict)


class RetrievalFilter(BaseModel):
    """Output of metadata PREFILTERING: an eligibility predicate that retrieval applies DURING search.

    conditions: payload field → allowed values, e.g. {"campus": ["SEOUL", "ALL"]}
    include_unknown: also allow chunks whose field is missing (unknown ≠ ineligible)
    """

    conditions: dict[str, list[str]]
    include_unknown: bool = True

    def matches(self, metadata: dict[str, Any]) -> bool:
        """True if a document with this metadata is eligible (the rule is in explain() below)."""
        return self.explain(metadata) is None

    def explain(self, metadata: dict[str, Any]) -> str | None:
        """Why a document is NOT eligible (None if it is). Same rule as the Qdrant filter:
        every condition must match one allowed value (a missing field passes if include_unknown)."""
        for field, allowed in self.conditions.items():
            values = metadata_values(metadata.get(field))
            if not values and not self.include_unknown:
                return f"{field} is unknown"
            if values and not set(values) & set(allowed):
                return f"{field}={'/'.join(values)} not in {allowed}"
        return None


class Candidate(BaseModel):
    """One retrieved chunk ID with its score (output of candidate retrieval).

    `score` is the score of the CURRENT ranking (cosine, BM25, RRF, …). `scores` keeps every score
    the candidate received so far, by name, e.g. {"dense": 0.83, "bm25": 12.4, "rrf": 0.032};
    scores of different kinds are never compared with each other.
    """

    rank: int
    chunk_id: str
    doc_id: str
    score: float
    scores: dict[str, float] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """Output of dense retrieval, lexical retrieval and hybrid fusion."""

    candidates: list[Candidate]
    applied_filter: RetrievalFilter | None = None  # the prefilter predicate that was really used
    details: dict[str, Any] = Field(default_factory=dict)  # extra information shown in the trace


class RemovedCandidate(BaseModel):
    chunk_id: str
    reason: str


class PostfilterResult(BaseModel):
    """Output of metadata POSTFILTERING: which retrieved candidates survived and which were removed."""

    kept: list[Candidate]
    removed: list[RemovedCandidate] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)  # e.g. how many came in, whether the list starved


class Evidence(BaseModel):
    """A candidate plus its text and source (output of metadata enrichment)."""

    rank: int
    chunk_id: str
    doc_id: str
    score: float
    text: str
    title: str
    source_uri: str
    section: str | None = None
    page_number: int | None = None
    token_count: int = 0
    scores: dict[str, float] = Field(default_factory=dict)  # see Candidate.scores
    label: str = ""  # "E1", "E2", … set by context construction
    applicability: dict[str, Any] = Field(default_factory=dict)  # AAES: condition, condition_status, superseded, label


class SufficiencyDecision(BaseModel):
    """Output of evidence sufficiency: may we answer with this evidence? (If not: abstain.)"""

    sufficient: bool
    reason: str
    signals: dict[str, Any] = Field(default_factory=dict)  # the observed values the decision used
    action: str | None = None  # AAES: ANSWER | CONDITIONAL | CLARIFY | ABSTAIN | CONFIRM (None for the plain gate)
    evidence_ids: list[str] | None = None  # AAES: the evidence the answer may use (None = all selected evidence)
    message: str | None = None  # AAES: the fixed reply for CLARIFY / ABSTAIN / CONFIRM (no generation)
    prompt_note: str | None = None  # AAES: added to the question for CONDITIONAL (one line per branch)


class PromptContext(BaseModel):
    """Output of context construction: everything generation needs."""

    messages: list[dict[str, str]]  # [{"role": "system", ...}, {"role": "user", ...}]
    context_text: str
    evidence: list[Evidence]  # the labelled evidence that is in the prompt
    token_count: int


class GenerationResult(BaseModel):
    """Output of generation."""

    answer: str
    model: str
    first_token_ms: float | None = None
    usage: dict[str, Any] = Field(default_factory=dict)  # token counts and timings reported by Ollama


class SourceReference(BaseModel):
    """A source shown under the answer. `cited` = the answer contains this source's [E#] label.

    This is source ATTRIBUTION (where the text came from), not proof that the sentence is true.
    """

    label: str
    cited: bool
    chunk_id: str
    doc_id: str
    title: str
    source_uri: str
    section: str | None
    page_number: int | None
    score: float
    excerpt: str


class FinalAnswer(BaseModel):
    """What the user sees."""

    answer: str
    outcome: str  # "answered" | "insufficient_context"
    sources: list[SourceReference] = Field(default_factory=list)


# =========================================================================== shared services


@dataclass
class Services:
    """Shared tools a block may use: `self.services.db`, `.embedder`, `.ollama`, `.settings`."""

    db: Database
    ollama: OllamaClient
    settings: Settings
    embedder: BaseEmbedder | None = None


# =========================================================================== stable IDs

ID_NAMESPACE = uuid.UUID("5d0f3d1e-6a4b-4f43-9c1e-8a3b2f6c7d10")


def make_doc_id(source_uri: str) -> str:
    """The same file path always gets the same doc_id."""
    return str(uuid.uuid5(ID_NAMESPACE, source_uri))


def make_chunk_id(doc_id: str, chunk_index: int, text: str) -> str:
    """Stable chunk ID. It is a UUID, so it is also a valid Qdrant point ID."""
    return str(uuid.uuid5(ID_NAMESPACE, f"{doc_id}:{chunk_index}:{hashlib.sha256(text.encode()).hexdigest()}"))
