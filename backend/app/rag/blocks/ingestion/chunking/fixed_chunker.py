"""IMPLEMENTED — fixed-size token windows over the whole document, ignoring section boundaries (O1)."""

from __future__ import annotations

import bisect

from app.rag.blocks.ingestion.chunking.base import BaseChunker
from app.rag.schemas import Chunk, ParsedDocument


class FixedTokenChunker(BaseChunker):
    """Hyperparameters: chunk_size, chunk_overlap (tokens).

    The document is read as ONE token stream (all sections joined). Windows of `chunk_size` tokens
    start every `chunk_size - chunk_overlap` tokens, wherever that falls — also in the middle of a
    section or across two sections. Compare with SectionTokenChunker to see what structure adds.
    A chunk's `section`/`page_number` are those of the section where the window starts.
    """

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        size, overlap = self.params["chunk_size"], self.params["chunk_overlap"]
        text, starts = document.full_text(), document.section_starts()
        offsets = self.services.embedder.token_offsets(text)
        chunks: list[Chunk] = []
        for first in range(0, len(offsets), size - overlap):
            last = min(first + size, len(offsets)) - 1
            start, end = offsets[first][0], offsets[last][1]
            section = document.sections[bisect.bisect_right(starts, start) - 1]
            chunks.append(Chunk(text=text[start:end], section=section.heading, page_number=section.page,
                                token_count=last - first + 1, start=start, end=end))  # fmt: skip
            if last == len(offsets) - 1:
                break
        return chunks
