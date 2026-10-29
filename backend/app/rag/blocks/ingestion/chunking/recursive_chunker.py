"""PLANNED — recursive character splitting (paragraphs → lines → sentences → words)."""

from __future__ import annotations

from app.rag.blocks.ingestion.chunking.base import BaseChunker
from app.rag.schemas import Chunk, ParsedDocument


class RecursiveChunker(BaseChunker):
    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        # TODO:
        # 1. Try to split each section at "\n\n"; if a piece is still longer than chunk_size tokens,
        #    split it at "\n", then at ". ", then at " ".
        # 2. Merge small neighbouring pieces until they reach chunk_size tokens.
        # 3. Return Chunk objects with real token counts (self.services.embedder.count_tokens).
        raise NotImplementedError("Recursive chunking is not implemented yet.")
