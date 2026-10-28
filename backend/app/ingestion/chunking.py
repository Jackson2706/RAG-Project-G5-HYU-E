"""Token-measured chunking with deterministic chunk IDs.

Token counts come from a real Hugging Face tokenizer (default: the embedding
model's own), using offset mappings so every chunk is an exact character span
of the normalized document text.

chunk_id = uuid5(doc_id | version_id | chunker_id | config_hash | span | sha256(text)),
so the same source version + chunking configuration always yields the same IDs.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from app.ingestion.loaders import sha256_bytes, stable_hash, stable_uuid
from app.models.documents import Chunk, ParsedBlock, ParsedDocument, SourceSpan

CHUNKER_REVISION = "v1"


class Tokenizer(Protocol):
    name: str

    def offsets(self, text: str) -> list[tuple[int, int]]: ...


class HFTokenizer:
    def __init__(self, tokenizer_id: str, revision: str | None = None) -> None:
        from transformers import AutoTokenizer

        self.name = tokenizer_id
        self._tok = AutoTokenizer.from_pretrained(tokenizer_id, revision=revision)
        if not self._tok.is_fast:
            raise ValueError(f"tokenizer '{tokenizer_id}' has no fast implementation with offset mappings")

    def offsets(self, text: str) -> list[tuple[int, int]]:
        enc = self._tok(text, add_special_tokens=False, return_offsets_mapping=True, verbose=False)
        return [(s, e) for s, e in enc["offset_mapping"] if e > s]


@lru_cache(maxsize=4)
def load_tokenizer(tokenizer_id: str, revision: str | None = None) -> HFTokenizer:
    return HFTokenizer(tokenizer_id, revision)


@dataclass
class _Piece:
    start: int
    end: int
    section_path: list[str]
    pages: list[int] = field(default_factory=list)
    heading_only: bool = False


class _TokenIndex:
    """Token offsets of a whole document with span → token-range lookups."""

    def __init__(self, offsets: list[tuple[int, int]]) -> None:
        self.offsets = offsets
        self.starts = [s for s, _ in offsets]
        self.ends = [e for _, e in offsets]

    def range(self, start: int, end: int) -> tuple[int, int]:
        return bisect.bisect_left(self.starts, start), bisect.bisect_right(self.ends, end)

    def count(self, start: int, end: int) -> int:
        a, b = self.range(start, end)
        return max(0, b - a)


def _windows(tokens: _TokenIndex, t0: int, t1: int, size: int, overlap: int) -> list[tuple[int, int]]:
    """Character spans of overlapping token windows over token range [t0, t1)."""
    spans = []
    step = size - overlap
    for ts in range(t0, t1, step):
        te = min(ts + size, t1)
        spans.append((tokens.offsets[ts][0], tokens.offsets[te - 1][1]))
        if te == t1:
            break
    return spans


def _block_at(blocks: list[ParsedBlock], pos: int) -> ParsedBlock | None:
    idx = bisect.bisect_right([b.span.start for b in blocks], pos) - 1
    return blocks[idx] if idx >= 0 else None


def structure_aware_pieces(doc: ParsedDocument, tokens: _TokenIndex, p: dict[str, Any]) -> list[_Piece]:
    size, overlap = p["chunk_size"], p["chunk_overlap"]
    min_size, max_size = p.get("min_chunk_size", 0), p.get("max_chunk_size", 512)
    pieces: list[_Piece] = []
    cur: _Piece | None = None

    def close() -> None:
        nonlocal cur
        if cur is None:
            return
        prev = pieces[-1] if pieces else None
        small = tokens.count(cur.start, cur.end) < min_size
        if (small and prev and not prev.heading_only and prev.section_path == cur.section_path
                and tokens.count(prev.start, cur.end) <= max_size):  # fmt: skip
            prev.end, prev.pages = cur.end, prev.pages + cur.pages
        else:
            pieces.append(cur)
        cur = None

    for block in doc.blocks:
        start, end = block.span.start, block.span.end
        pages = [block.page_number] if block.page_number else []
        n = tokens.count(start, end)
        if block.kind == "heading":
            # A heading opens a new piece; consecutive headings stay together and carry into the content.
            if cur is not None and not cur.heading_only:
                close()
            if cur is None:
                cur = _Piece(start, end, block.section_path, pages, heading_only=True)
            else:
                cur.end, cur.section_path = end, block.section_path
            continue
        if n > max_size:
            heading_start = cur.start if cur is not None and cur.heading_only else None
            if heading_start is None:
                close()
            cur = None
            t0, t1 = tokens.range(start, end)
            for i, (ws, we) in enumerate(_windows(tokens, t0, t1, size, overlap)):
                ws = heading_start if i == 0 and heading_start is not None else ws
                pieces.append(_Piece(ws, we, block.section_path, pages))
            continue
        standalone = block.kind == "table"  # parser emits table blocks only when preserve_tables is on
        if cur is not None:
            if cur.heading_only:
                if tokens.count(cur.start, end) > max_size:
                    close()
            elif tokens.count(cur.start, end) > size or cur.section_path != block.section_path or standalone:
                close()
        if cur is None:
            cur = _Piece(start, end, block.section_path, pages)
        else:
            cur.end, cur.heading_only = end, False
            cur.pages += pages
        if standalone:
            close()
    close()
    return pieces


def fixed_pieces(doc: ParsedDocument, tokens: _TokenIndex, p: dict[str, Any]) -> list[_Piece]:
    pieces = []
    for start, end in _windows(tokens, 0, len(tokens.offsets), p["chunk_size"], p["chunk_overlap"]):
        first = _block_at(doc.blocks, start)
        pages = sorted({b.page_number for b in doc.blocks if b.page_number and b.span.start < end and b.span.end > start})
        pieces.append(_Piece(start, end, first.section_path if first else [], pages))
    return pieces


def chunk_document(
    doc: ParsedDocument, doc_id: str, version_id: str, method: str, params: dict[str, Any], tokenizer: Tokenizer
) -> list[Chunk]:
    builders = {"structure_aware": structure_aware_pieces, "fixed": fixed_pieces}
    if method not in builders:
        raise ValueError(f"chunking method '{method}' is not implemented")
    tokens = _TokenIndex(tokenizer.offsets(doc.content))
    if not tokens.offsets:
        return []
    chunker_id = f"{method}-{CHUNKER_REVISION}"
    config_hash = stable_hash({"method": method, "params": params, "tokenizer": tokenizer.name})[:12]
    chunks: list[Chunk] = []
    for piece in builders[method](doc, tokens, params):
        text = doc.content[piece.start : piece.end]
        path = piece.section_path
        header = None
        if params.get("preserve_headings", True):
            parts = ([doc.title] if doc.title and (not path or path[0] != doc.title) else []) + path
            header = " > ".join(parts) or None
        label = "|".join([doc_id, version_id, chunker_id, config_hash, str(piece.start), str(piece.end), sha256_bytes(text.encode())])
        chunks.append(Chunk(
            chunk_id=stable_uuid(label), doc_id=doc_id, version_id=version_id, chunk_index=len(chunks), text=text,
            context_header=header, section_title=path[-1] if path else None, section_path=path,
            page_number=min(piece.pages) if piece.pages else None, page_end=max(piece.pages) if piece.pages else None,
            source_span=SourceSpan(start=piece.start, end=piece.end), token_count=tokens.count(piece.start, piece.end),
            chunker_id=chunker_id, chunker_config_hash=config_hash,
        ))  # fmt: skip
    return chunks
