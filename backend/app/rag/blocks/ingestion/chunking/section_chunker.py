"""IMPLEMENTED — one chunk per section; long sections are cut into overlapping token windows."""

from __future__ import annotations

from app.rag.blocks.ingestion.chunking.base import BaseChunker
from app.rag.schemas import Chunk, ParsedDocument


class SectionTokenChunker(BaseChunker):
    """Hyperparameters: chunk_size, chunk_overlap (tokens).

    A section with at most `chunk_size` tokens stays one chunk. A longer section is cut into windows of
    `chunk_size` tokens; each window starts `chunk_size - chunk_overlap` tokens after the previous one.
    """

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        size, overlap = self.params["chunk_size"], self.params["chunk_overlap"]
        embedder = self.services.embedder
        chunks: list[Chunk] = []
        for section in document.sections:
            offsets = embedder.token_offsets(section.text)
            if len(offsets) <= size:  # short section: keep it whole
                chunks.append(Chunk(text=section.text, section=section.heading, page_number=section.page, token_count=len(offsets)))
                continue
            for first in range(0, len(offsets), size - overlap):
                last = min(first + size, len(offsets)) - 1
                text = section.text[offsets[first][0] : offsets[last][1]]
                chunks.append(Chunk(text=text, section=section.heading, page_number=section.page, token_count=last - first + 1))
                if last == len(offsets) - 1:
                    break
        return chunks
