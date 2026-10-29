"""Abstract class for Chunking."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import Chunk, ParsedDocument


class BaseChunker(PipelineBlock):
    """Split a parsed document into chunks.

    Input:  ParsedDocument
    Output: list[Chunk] (text, section, page_number, token_count)
    Token counts must come from the embedder's tokenizer: self.services.embedder.token_offsets(text).
    """

    @abstractmethod
    def chunk(self, document: ParsedDocument) -> list[Chunk]: ...
