"""IMPLEMENTED — recursive splitting: sections → paragraphs → lines → sentences → words, merged up to a token limit (O5)."""

from __future__ import annotations

from app.rag.blocks.ingestion.chunking.base import BaseChunker
from app.rag.schemas import Chunk, ParsedDocument

SEPARATORS = ["\n\n", "\n", ". ", " "]  # tried in this order: the most "structural" cut first


class RecursiveChunker(BaseChunker):
    """Hyperparameters: chunk_size, chunk_overlap (tokens, counted with the embedder's tokenizer).

    1. Each section is handled on its own (chunks never cross a section boundary).
    2. A piece longer than `chunk_size` tokens is split at blank lines; pieces still too long are
       split at line breaks, then at ". ", then at spaces (a single over-long word is cut by tokens).
    3. Neighbouring pieces are merged again while the chunk stays within `chunk_size` tokens.
       A new chunk starts with the last pieces of the previous chunk, up to `chunk_overlap` tokens.
    """

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        for section, base in zip(document.sections, document.section_starts(), strict=True):
            pieces = self._split(section.text, 0, len(section.text), 0)
            for start, end in self._merge(section.text, pieces):
                text = section.text[start:end]
                chunks.append(Chunk(text=text, section=section.heading, page_number=section.page,
                                    token_count=self._tokens(text), start=base + start, end=base + end))  # fmt: skip
        return chunks

    def _tokens(self, text: str) -> int:
        return self.services.embedder.count_tokens(text)

    def _split(self, text: str, start: int, end: int, level: int) -> list[tuple[int, int]]:
        """Spans (start, end) of pieces of text[start:end] that each fit chunk_size tokens."""
        size = self.params["chunk_size"]
        if self._tokens(text[start:end]) <= size:
            return [(start, end)]
        if level == len(SEPARATORS):  # no separator left: cut by tokens
            offsets = self.services.embedder.token_offsets(text[start:end])
            return [(start + offsets[i][0], start + offsets[min(i + size, len(offsets)) - 1][1]) for i in range(0, len(offsets), size)]
        separator, pieces, position = SEPARATORS[level], [], start
        while position < end:
            cut = text.find(separator, position, end)
            cut = end if cut == -1 else cut + len(separator)  # the separator stays with the piece before it
            pieces.extend(self._split(text, position, cut, level + 1))
            position = cut
        return pieces

    def _merge(self, text: str, pieces: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Greedily join neighbouring pieces up to chunk_size tokens; start each chunk with an overlap."""
        size, overlap = self.params["chunk_size"], self.params["chunk_overlap"]
        counted = [(s, e, self._tokens(text[s:e])) for s, e in pieces if text[s:e].strip()]
        spans: list[tuple[int, int]] = []
        current: list[tuple[int, int, int]] = []
        for piece in counted:
            if current and self._tokens(text[current[0][0] : piece[1]]) > size:
                spans.append((current[0][0], current[-1][1]))
                carried, total = [], 0
                for previous in reversed(current):  # overlap: the last pieces, up to `overlap` tokens
                    if total + previous[2] > overlap:
                        break
                    carried.insert(0, previous)
                    total += previous[2]
                current = carried if carried and self._tokens(text[carried[0][0] : piece[1]]) <= size else []
            current.append(piece)
        if current:
            spans.append((current[0][0], current[-1][1]))
        return [self._strip(text, s, e) for s, e in spans]

    @staticmethod
    def _strip(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end
