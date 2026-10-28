"""Persistent document-side records: MongoDB `documents`, `chunks`, `extracted_facts`, `index_revisions`."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

BlockKind = Literal["heading", "paragraph", "list", "table"]
IngestionStatus = Literal["parsed", "indexed", "failed"]
RevisionStatus = Literal["building", "verified", "active", "failed", "superseded"]


class SourceSpan(BaseModel):
    """Character offsets `[start, end)` into the version's normalized text (`SourceDocument.content`)."""

    start: int
    end: int


class ParsedBlock(BaseModel):
    kind: BlockKind
    text: str
    section_path: list[str] = Field(default_factory=list)
    page_number: int | None = None
    span: SourceSpan


class ParsedDocument(BaseModel):
    """Parser output. `content` is the normalized text every span refers to."""

    title: str | None
    content: str
    blocks: list[ParsedBlock]
    page_count: int | None = None
    declared_metadata: dict[str, Any] = Field(default_factory=dict)
    parser_id: str
    warnings: list[str] = Field(default_factory=list)


class SourceDocument(BaseModel):
    """One logical source (`doc_id`) at one content version (`version_id`)."""

    doc_id: str
    source_uri: str
    file_path: str
    title: str | None = None
    media_type: str
    size_bytes: int
    language: str | None = None
    issuer: str | None = None
    document_type: str | None = None
    campus: str | None = None
    audience: list[str] = Field(default_factory=list)
    academic_year: str | None = None
    publication_date: str | None = None
    effective_from: str | None = None
    effective_until: str | None = None
    topics: list[str] = Field(default_factory=list)
    metadata_provenance: dict[str, str] = Field(
        default_factory=dict, description="field -> 'declared' | 'rule' | 'configured_default'"
    )
    source_sha256: str
    parser_id: str
    version_id: str
    page_count: int | None = None
    content: str = Field(description="Normalized text; chunk source spans index into this string.")
    parse_warnings: list[str] = Field(default_factory=list)
    ingestion_status: IngestionStatus = "parsed"
    ingestion_errors: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    version_id: str
    chunk_index: int
    text: str = Field(description="Exact slice content[source_span.start:source_span.end].")
    context_header: str | None = Field(
        default=None, description="Heading path prepended to the text for embedding/BM25 when preserve_headings is on."
    )
    section_title: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_number: int | None = None
    page_end: int | None = None
    source_span: SourceSpan
    token_count: int
    chunker_id: str
    chunker_config_hash: str
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Retrieval metadata copied from the document.")
    index_revisions: list[str] = Field(default_factory=list)

    @property
    def embedding_text(self) -> str:
        return f"{self.context_header}\n{self.text}" if self.context_header else self.text


class ExtractedFact(BaseModel):
    """Schema for future LLM/rule fact extraction. No records are produced by the MVP."""

    fact_id: str
    doc_id: str
    chunk_id: str
    fact_type: str
    subject: str
    predicate: str
    object: str
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    valid_from: str | None = None
    valid_until: str | None = None
    evidence_span: SourceSpan
    extraction_method: str
    review_status: Literal["unreviewed", "accepted", "rejected"] = "unreviewed"


class EmbeddingContract(BaseModel):
    """Everything that must match between stored vectors and query vectors."""

    provider: str
    model_id: str
    model_revision: str | None
    dimension: int
    normalize: bool
    distance: str
    query_instruction: str
    max_seq_length: int | None = None

    def contract_hash(self) -> str:
        from app.ingestion.loaders import stable_hash

        return stable_hash(self.model_dump())


class IndexRevision(BaseModel):
    revision_id: str
    collection_name: str
    status: RevisionStatus
    embedding: EmbeddingContract
    offline_config: dict[str, Any]
    doc_versions: dict[str, str] = Field(description="doc_id -> version_id included in this revision")
    doc_count: int
    chunk_count: int
    vectors_reused: int = 0
    vectors_computed: int = 0
    verification: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    activated_at: datetime | None = None
