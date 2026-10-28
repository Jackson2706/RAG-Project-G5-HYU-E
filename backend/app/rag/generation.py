"""Grounded prompt construction and basic citation verification."""

from __future__ import annotations

import json
import re
from typing import Any

from app.ingestion.chunking import Tokenizer
from app.models.documents import Chunk, SourceDocument
from app.models.pipeline import Candidate, Citation, CitationReport

INSUFFICIENT_MARKER = "INSUFFICIENT_CONTEXT"
CITATION_GROUP = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S?\d+)*)\s*\]")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

SYSTEM_PROMPT = f"""You are HYU Compass, an assistant for new students at Hanyang University (HYU).
Answer using ONLY the numbered sources provided with the question.
Rules:
- Support every factual statement with the label of the source it comes from, e.g. [S1] or [S1][S3].
- Use only labels that appear in the sources. Never invent sources, URLs, dates, or page numbers.
- If the sources do not contain the information needed, reply with the single word {INSUFFICIENT_MARKER} on the first line, then one sentence saying what is missing.
- If the sources only partly answer the question, answer that part and say what is not covered.
- Do not use outside knowledge. Write clear, concise English in Markdown."""


def _location(c: Candidate) -> str:
    parts = [c.title or c.source_uri or c.doc_id]
    if c.section_path and c.section_path != [c.title]:
        parts.append(" › ".join(p for p in c.section_path if p != c.title))
    if c.page_number:
        parts.append(f"page {c.page_number}" if c.page_end in (None, c.page_number) else f"pages {c.page_number}–{c.page_end}")
    return " — ".join(p for p in parts if p)


def build_context(
    evidence: list[Candidate], method: str, params: dict[str, Any], tokenizer: Tokenizer | None
) -> tuple[str, list[Citation], dict[str, Any]]:
    """Format evidence as labelled sources within the context token budget.

    Returns (context_text, citations, stats). Evidence that does not fit is truncated
    (last fitting source) or dropped, and reported in stats.
    """
    if method not in ("standard", "structured"):
        raise ValueError(f"context method '{method}' is not implemented")
    budget = params["max_context_tokens"]
    count = (lambda s: len(tokenizer.offsets(s))) if tokenizer else (lambda s: len(s.split()))
    blocks: list[str] = []
    citations: list[Citation] = []
    used, truncated, dropped = 0, [], []
    for i, c in enumerate(evidence, start=1):
        marker = f"S{i}"
        body = c.text or ""
        meta = {k: v for k, v in c.metadata.items() if v not in (None, [], "")} if params["include_source_metadata"] else {}
        header_tokens = 40 if params["include_source_metadata"] else 8
        remaining = budget - used - header_tokens
        if remaining <= 20:
            dropped.append(c.chunk_id)
            continue
        if count(body) > remaining:
            offsets = tokenizer.offsets(body) if tokenizer else None
            body = body[: offsets[remaining - 1][1]] + " …" if offsets else " ".join(body.split()[:remaining]) + " …"
            truncated.append(c.chunk_id)
        if method == "standard":
            header = f"[{marker}] {_location(c)}" if params["include_source_metadata"] else f"[{marker}]"
            if meta:
                header += "\n(" + "; ".join(f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in meta.items()) + ")"
            block = f"{header}\n{body}"
        else:
            obj: dict[str, Any] = {"id": marker}
            if params["include_source_metadata"]:
                obj.update(title=c.title, section=" › ".join(c.section_path) or None, page=c.page_number, **meta)
            obj["text"] = body
            block = json.dumps({k: v for k, v in obj.items() if v is not None}, ensure_ascii=False, indent=1)
        used += count(block)
        blocks.append(block)
        citations.append(Citation(marker=marker, chunk_id=c.chunk_id, doc_id=c.doc_id, title=c.title, source_uri=c.source_uri,
                                  section_path=c.section_path, page_number=c.page_number, source_span=c.source_span,
                                  excerpt=(c.text or "")[:600]))  # fmt: skip
    separator = "\n\n" if method == "standard" else ",\n"
    text = separator.join(blocks) if method == "standard" else "[\n" + separator.join(blocks) + "\n]"
    return text, citations, {"context_tokens": used, "budget": budget, "truncated": truncated, "dropped": dropped}


def build_messages(question: str, context_text: str) -> list[dict[str, str]]:
    user = f"Sources:\n{context_text}\n\nQuestion: {question}\n\nAnswer with citations:"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def cited_markers(answer: str) -> list[str]:
    markers: list[str] = []
    for group in CITATION_GROUP.findall(answer):
        for part in re.split(r"\s*[,;]\s*", group):
            markers.append(part if part.startswith("S") else f"S{part}")
    return list(dict.fromkeys(markers))


def verify_citations(
    answer: str, citations: list[Citation], chunks: dict[str, Chunk], documents: dict[str, SourceDocument], verify_spans: bool
) -> tuple[list[Citation], CitationReport]:
    """Identity and span checks. Does NOT judge whether the cited passage supports the sentence."""
    by_marker = {c.marker: c for c in citations}
    markers = cited_markers(answer)
    report = CitationReport(method="id_span")
    report.cited_markers = [m for m in markers if m in by_marker]
    report.invalid_markers = [m for m in markers if m not in by_marker]
    out = []
    for c in citations:
        c = c.model_copy()
        c.cited = c.marker in markers
        chunk, doc = chunks.get(c.chunk_id), documents.get(c.doc_id)
        c.resolved = chunk is not None and doc is not None and doc.version_id == chunk.version_id
        if not c.resolved:
            report.unresolved.append(c.marker)
        elif verify_spans:
            span = chunk.source_span
            c.span_verified = doc.content[span.start : span.end] == chunk.text
            if not c.span_verified:
                report.span_failures.append(c.marker)
        if not c.cited:
            report.uncited_evidence.append(c.marker)
        out.append(c)
    sentences = [s for s in SENTENCE_SPLIT.split(answer) if len(s.strip()) > 20 and not s.strip().startswith("#")]
    report.sentences_total = len(sentences)
    report.sentences_with_citation = sum(1 for s in sentences if CITATION_GROUP.search(s))
    return out, report
