"""IMPLEMENTED — no chunking: the whole document is one retrieval unit (BEIR Protocol A)."""

from __future__ import annotations

from app.rag.blocks.ingestion.chunking.base import BaseChunker
from app.rag.schemas import Chunk, ParsedDocument


class WholeDocumentChunker(BaseChunker):
    """One chunk per document, so retrieval ranks original documents directly (the BEIR setting).

    The embedding model only reads its first `max_seq_length` tokens (BGE: 512). Longer documents are
    represented by their beginning; ingestion reports how many units were truncated.
    """

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        text = document.full_text()
        first = document.sections[0] if document.sections else None
        return [Chunk(text=text, section=None, page_number=first.page if first else None,
                      token_count=self.services.embedder.count_tokens(text), start=0, end=len(text))]  # fmt: skip
