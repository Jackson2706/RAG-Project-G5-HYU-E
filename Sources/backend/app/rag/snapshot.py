"""Frozen HYU snapshot → ParsedDocument, plus what the applicability tagger needs per chunk.

A snapshot row (Report/data/HYU/snapshots/<id>/documents.jsonl) has `text` and `spans`
(kind heading / paragraph / table_row / list_item / attachment, with char offsets into `text`).

- Every `heading` span with English text starts a new Section. Headers are English-only
  (PLAYBOOK A4): a Korean heading stays in the body and the previous English heading is kept.
- A section is also cut at a span boundary when it would grow past `max_tokens`, so the chunker
  never has to split a table row or paragraph that fits on its own (same heading, next section).
- `SpanLookup` maps a chunk's character range back to the spans it covers: their kinds and the
  heading path. That is the input of `tag_chunk`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import DATA_DIR
from app.rag.schemas import SECTION_SEPARATOR, Chunk, ParsedDocument, Section, make_doc_id

HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
TITLE_WRAPPER = re.compile(r"^\s*/\s*(.+?)\s*/")  # Seoul board titles: "/ Undergraduate Admission Guideline / …"
LINE = "\n"  # spans inside a section are joined by one newline


def snapshot_dir(snapshot_id: str) -> Path:
    return DATA_DIR / "HYU" / "snapshots" / snapshot_id


def is_english(text: str | None) -> bool:
    return bool(text and text.strip() and not HANGUL.search(text) and re.search(r"[A-Za-z]", text))


def clean_title(title: str) -> str:
    match = TITLE_WRAPPER.match(title or "")
    return match.group(1) if match else (title or "").strip()


@dataclass
class SpanInfo:
    start: int  # offsets into ParsedDocument.full_text()
    end: int
    kind: str
    heading_path: list[str]
    snapshot_start: int  # offsets into the snapshot row's text
    snapshot_end: int


class SpanLookup:
    def __init__(self, spans: list[SpanInfo]) -> None:
        self.spans = spans

    def covered(self, start: int, end: int) -> list[SpanInfo]:
        return [s for s in self.spans if s.start < end and start < s.end]

    def chunk_input(self, document: ParsedDocument, chunk: Chunk) -> dict:
        """The dict `tag_chunk` expects for one chunk of this document."""
        spans = self.covered(chunk.start or 0, chunk.end or 0)
        kinds = {s.kind for s in spans}
        kind = "table_row" if kinds == {"table_row"} else (kinds.pop() if len(kinds) == 1 else "mixed")
        meta = document.declared_metadata
        return {"doc_id": meta.get("doc_id"), "site": meta["site"], "title": document.title, "source_uri": document.source_uri,
                "post_date": meta.get("post_date") or None, "superseded_by": meta.get("superseded_by") or None, "kind": kind,
                "heading_path": spans[0].heading_path if spans else [], "text": chunk.text,
                "source_spans": [[s.snapshot_start, s.snapshot_end] for s in spans]}  # fmt: skip


def to_parsed_document(row: dict, snapshot_id: str, count_tokens: Callable[[str], int] | None = None,
                       max_tokens: int = 320) -> tuple[ParsedDocument, SpanLookup]:  # fmt: skip
    text = row["text"]
    english_headings = [text[s["char_start"]:s["char_end"]].strip() for s in row["spans"] if s["kind"] == "heading"]
    english_headings = [h for h in english_headings if is_english(h)]
    title = clean_title(row["title"])
    if not is_english(title):
        title = english_headings[0] if english_headings else (title or row["source_uri"])

    sections: list[tuple[str | None, list[tuple[str, str, list[str], int, int]]]] = []
    path: list[str] = []
    heading: str | None = title if is_english(title) else None

    def section_text(items):
        return LINE.join(item[0] for item in items)

    for span in row["spans"]:
        piece = text[span["char_start"]:span["char_end"]].strip()
        if not piece:
            continue
        if span["kind"] == "heading" and is_english(piece):
            heading = piece
            # shortcut: the crawler records no heading levels, so the path is the last two English headings
            path = [*path[-1:], piece]
            sections.append((heading, []))
            continue
        if not sections:
            sections.append((heading, []))
        items = sections[-1][1]
        if items and count_tokens and count_tokens(section_text(items) + LINE + piece) > max_tokens:
            sections.append((heading, []))
            items = sections[-1][1]
        items.append((piece, span["kind"], list(path), span["char_start"], span["char_end"]))

    sections = [(h, items) for h, items in sections if items]
    parsed_sections, lookup, position = [], [], 0
    for h, items in sections:
        offset = position
        for piece, kind, span_path, snapshot_start, snapshot_end in items:
            lookup.append(SpanInfo(start=offset, end=offset + len(piece), kind=kind, heading_path=span_path,
                                   snapshot_start=snapshot_start, snapshot_end=snapshot_end))  # fmt: skip
            offset += len(piece) + len(LINE)
        body = section_text(items)
        parsed_sections.append(Section(heading=h, text=body))
        position += len(body) + len(SECTION_SEPARATOR)

    declared = {"doc_id": make_doc_id(row["source_uri"]), "snapshot_doc_id": row.get("snapshot_doc_id", row["doc_id"]), "site": row["site"], "campus": row["campus"], "snapshot_id": snapshot_id,
                "source_sha256": row["source_sha256"], "post_date": row.get("post_date") or "",
                "superseded_by": row.get("superseded_by") or ""}  # fmt: skip
    if title != row["title"]:
        declared["title_original"] = row["title"]
    document = ParsedDocument(path=Path(f"snapshot/{snapshot_id}/{row['doc_id']}"), source_uri=row["source_uri"], file_type="hyu_snapshot",
                              title=title, sections=parsed_sections, declared_metadata=declared)  # fmt: skip
    return document, SpanLookup(lookup)


def load_snapshot(snapshot_id: str, count_tokens: Callable[[str], int] | None = None,
                  max_tokens: int = 320) -> list[tuple[ParsedDocument, SpanLookup]]:  # fmt: skip
    folder = snapshot_dir(snapshot_id)
    if not (folder / "documents.jsonl").exists():
        raise FileNotFoundError(f"Snapshot {snapshot_id} not found in {folder}")
    with open(folder / "documents.jsonl", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    # The index derives its own doc_id from source_uri (make_doc_id), so `superseded_by` is converted
    # from the snapshot's doc_id to the index doc_id of the newer version; the snapshot id is kept too.
    index_id_of = {r["doc_id"]: make_doc_id(r["source_uri"]) for r in rows}
    rows = [{**r, "snapshot_doc_id": r["doc_id"], "superseded_by": index_id_of.get(r["superseded_by"], r["superseded_by"])}
            if r.get("superseded_by") else {**r, "snapshot_doc_id": r["doc_id"]} for r in rows]  # fmt: skip
    return [to_parsed_document(r, snapshot_id, count_tokens, max_tokens) for r in rows]


def source_spans_match(chunk_text: str, snapshot_text: str, source_spans: list[list[int]]) -> bool:
    """Match a whole-span chunk exactly, or a one-span token window as a substring."""
    pieces = []
    for span in source_spans:
        if not isinstance(span, (list, tuple)) or len(span) != 2:
            return False
        start, end = span
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start <= end <= len(snapshot_text):
            return False
        pieces.append(snapshot_text[start:end].strip())
    if not pieces:
        return False
    joined = LINE.join(pieces)
    return chunk_text == joined or (len(pieces) == 1 and bool(chunk_text) and chunk_text in joined)


def evaluate_checks(facts: dict) -> tuple[dict[str, bool], str]:
    """VERIFY: every check is pass/fail; the index is "verified" only if all pass, else it stays "built"."""
    checks = {
        "documents_expected": facts["mongo_documents"] == facts["expected_documents"],
        "chunks_equal_points": facts["mongo_chunks"] == facts["qdrant_points"] > 0,
        "dimension_384": facts["dimension"] == 384,
        "chunk_ids_unique": facts["unique_chunk_ids"] == facts["mongo_chunks"],
        "every_point_has_chunk": facts["points_without_chunk"] == 0,
        "max_tokens_le_512": facts["max_embedded_tokens"] <= 512,
        "truncated_zero": facts["truncated_by_embedder"] == 0,
        "applicability_valid": facts["invalid_applicability"] == 0,
        "llm_errors_zero": facts["llm_errors"] == 0 and facts["partition"].get("llm_errors", 0) == 0,
        # every chunk in exactly one known bucket (rule_tagged … llm_errors), summing to the chunk count
        "partition_complete": sum(facts["partition"].values()) == facts["mongo_chunks"] and None not in facts["partition"],
        "span_text_matches": facts["span_text_mismatches"] == 0,
        "payload_has_scope_campus": facts["points_missing_app_fields"] == 0,
        "no_unmasked_emails": facts["unmasked_emails"] == 0,
        "no_hangul_headers": facts["hangul_headers"] == 0,
        "default_index_unchanged": facts["default_before"] == facts["default_after"],
    }
    return checks, "verified" if all(checks.values()) else "built"
