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
    source_uri: str  # path relative to data/, e.g. "raw/handbook.pdf"
    file_type: str  # "pdf" | "txt" | "md" | "html"
    title: str
    sections: list[Section]
    declared_metadata: dict[str, str] = Field(default_factory=dict)  # e.g. Markdown front matter


class DocumentMetadata(BaseModel):
    """Output of metadata extraction. Unknown values stay missing — never guessed."""

    title: str
    language: str
    extra: dict[str, str] = Field(default_factory=dict)


class Chunk(BaseModel):
    """Output of chunking: one searchable piece of a document."""

    text: str
    section: str | None
    page_number: int | None
    token_count: int


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
        return {k: v for k, v in self.model_dump().items() if v is not None}


class QueryAnalysis(BaseModel):
    """Output of query understanding: what the question asks for."""

    intent: str | None = None
    criteria: FilterCriteria = Field(default_factory=FilterCriteria)


class RewrittenQuery(BaseModel):
    """Output of query rewriting. `query` is used for retrieval; the original question is kept for the prompt."""

    query: str
    alternatives: list[str] = Field(default_factory=list)  # extra queries (multi-query rewriting)


class RetrievalFilter(BaseModel):
    """Output of metadata PREFILTERING: an eligibility predicate that retrieval applies DURING search.

    conditions: payload field → allowed values, e.g. {"campus": ["SEOUL", "ALL"]}
    include_unknown: also allow chunks whose field is missing (unknown ≠ ineligible)
    """

    conditions: dict[str, list[str]]
    include_unknown: bool = True


class Candidate(BaseModel):
    """One retrieved chunk ID with its score (output of candidate retrieval)."""

    rank: int
    chunk_id: str
    doc_id: str
    score: float


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
    label: str = ""  # "E1", "E2", … set by context construction


class SufficiencyDecision(BaseModel):
    """Output of evidence sufficiency: may we answer with this evidence? (If not: abstain.)"""

    sufficient: bool
    reason: str


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
