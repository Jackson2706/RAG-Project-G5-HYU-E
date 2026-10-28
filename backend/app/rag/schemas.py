"""The data that flows between pipeline blocks.

Each block's abstract method says which of these types it receives and returns, so you
always know what you get and what you must give back. They are plain dataclasses: create
them like `Candidate(rank=1, chunk_id="…", doc_id="…", score=0.83)`.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # only for type hints; avoids import cycles
    from app.config import Settings
    from app.database import Database
    from app.ollama import OllamaClient
    from app.rag.blocks.embedding import BaseEmbedder


# --------------------------------------------------------------------------- offline (ingestion)


@dataclass
class Section:
    """A piece of a document under one heading (or one PDF page)."""

    heading: str | None
    text: str
    page: int | None = None


@dataclass
class ParsedDocument:
    """Output of a parser: the readable content of one file."""

    path: Path
    source_uri: str  # path relative to data/, e.g. "raw/handbook.pdf"
    file_type: str  # "pdf" | "txt" | "md" | "html"
    title: str
    sections: list[Section]
    declared_metadata: dict[str, str] = field(default_factory=dict)  # e.g. Markdown front matter


@dataclass
class DocumentMetadata:
    """Output of a metadata extractor. Unknown values stay None/empty — never guessed."""

    title: str
    language: str
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class Chunk:
    """Output of a chunker: one searchable piece of a document."""

    text: str
    section: str | None
    page_number: int | None
    token_count: int


# --------------------------------------------------------------------------- online (questions)


@dataclass
class QueryAnalysis:
    """Output of query understanding (future): what the question asks for."""

    constraints: dict[str, str] = field(default_factory=dict)  # e.g. {"campus": "ERICA"}


@dataclass
class Candidate:
    """One retrieved chunk ID with its score (output of dense/lexical retrieval and fusion)."""

    rank: int
    chunk_id: str
    doc_id: str
    score: float


@dataclass
class RetrievalResult:
    """Output of a retriever."""

    candidates: list[Candidate]
    details: dict[str, Any] = field(default_factory=dict)  # extra information shown in the trace


@dataclass
class Evidence:
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
    label: str = ""  # "E1", "E2", … set by the context builder


@dataclass
class SufficiencyDecision:
    """Output of a sufficiency gate (future): may we answer with this evidence?"""

    sufficient: bool
    reason: str


@dataclass
class PromptContext:
    """Output of the context builder: everything the generator needs."""

    messages: list[dict[str, str]]  # [{"role": "system", ...}, {"role": "user", ...}]
    context_text: str
    evidence: list[Evidence]  # the labelled evidence that is in the prompt
    token_count: int


@dataclass
class GenerationResult:
    """Output of a generator."""

    answer: str
    model: str
    first_token_ms: float | None = None


@dataclass
class Citation:
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


@dataclass
class CitationResult:
    """Output of a citation verifier."""

    answer: str  # the answer with invalid markers removed
    citations: list[Citation]
    invalid_markers: list[str]


@dataclass
class FinalAnswer:
    """Output of the response guard: what the user sees."""

    answer: str
    outcome: str  # "answered" | "insufficient_context"
    citations: list[Citation]


# --------------------------------------------------------------------------- shared services


@dataclass
class Services:
    """Shared tools a block may use: `self.services.db`, `.embedder`, `.ollama`, `.settings`."""

    db: Database
    ollama: OllamaClient
    settings: Settings
    embedder: BaseEmbedder | None = None


# --------------------------------------------------------------------------- stable IDs

ID_NAMESPACE = uuid.UUID("5d0f3d1e-6a4b-4f43-9c1e-8a3b2f6c7d10")


def make_doc_id(source_uri: str) -> str:
    """The same file path always gets the same doc_id."""
    return str(uuid.uuid5(ID_NAMESPACE, source_uri))


def make_chunk_id(doc_id: str, chunk_index: int, text: str) -> str:
    """Stable chunk ID. It is a UUID, so it is also a valid Qdrant point ID."""
    return str(uuid.uuid5(ID_NAMESPACE, f"{doc_id}:{chunk_index}:{hashlib.sha256(text.encode()).hexdigest()}"))
