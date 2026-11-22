"""PLANNED — cut where the topic changes instead of at a fixed size."""

from __future__ import annotations

from app.rag.blocks.ingestion.chunking.base import BaseChunker
from app.rag.schemas import Chunk, ParsedDocument


class SemanticChunker(BaseChunker):
    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        # TODO:
        # 1. Split each section into sentences.
        # 2. Embed every sentence with self.services.embedder.embed_documents(...).
        # 3. Start a new chunk where two neighbouring sentences are not similar.
        raise NotImplementedError("Semantic chunking is not implemented yet.")
