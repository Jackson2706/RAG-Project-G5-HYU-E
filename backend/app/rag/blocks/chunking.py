"""Block: Chunking — split a document into small searchable pieces."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.base import PipelineBlock
from app.rag.schemas import Chunk, ParsedDocument


class BaseChunker(PipelineBlock):
    """Split a parsed document into chunks.

    Input:  ParsedDocument
    Output: list[Chunk] (text, section, page_number, token_count)
    Token counts must come from the embedder's tokenizer: self.services.embedder.token_offsets(text).
    """

    @abstractmethod
    def chunk(self, document: ParsedDocument) -> list[Chunk]: ...


class SectionTokenChunker(BaseChunker):
    """IMPLEMENTED — one chunk per section; long sections are cut into overlapping token windows.

    Hyperparameters: chunk_size, chunk_overlap (tokens). A window starts
    `chunk_size - chunk_overlap` tokens after the previous one.
    """

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        size, overlap = self.params["chunk_size"], self.params["chunk_overlap"]
        embedder = self.services.embedder
        chunks: list[Chunk] = []
        for section in document.sections:
            offsets = embedder.token_offsets(section.text)
            if len(offsets) <= size:  # short section: keep it whole
                chunks.append(Chunk(section.text, section.heading, section.page, len(offsets)))
                continue
            for first in range(0, len(offsets), size - overlap):
                last = min(first + size, len(offsets)) - 1
                text = section.text[offsets[first][0] : offsets[last][1]]
                chunks.append(Chunk(text, section.heading, section.page, last - first + 1))
                if last == len(offsets) - 1:
                    break
        return chunks


class SemanticChunker(BaseChunker):
    """PLANNED — cut where the topic changes instead of at a fixed size."""

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        # TODO:
        # 1. Split each section into sentences.
        # 2. Embed every sentence with self.services.embedder.embed_documents(...).
        # 3. Start a new chunk where two neighbouring sentences are not similar.
        raise NotImplementedError("Semantic chunking is not implemented yet.")
