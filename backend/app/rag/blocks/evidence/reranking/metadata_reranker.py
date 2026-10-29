"""PLANNED — move evidence that matches the student's situation (campus, year) up."""

from __future__ import annotations

from app.rag.blocks.evidence.reranking.base import BaseReranker
from app.rag.schemas import Evidence


class MetadataAwareReranker(BaseReranker):
    async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]:
        # TODO: add a bonus to the score of evidence whose document metadata matches the question,
        # then sort and renumber rank. Unlike filtering, nothing is removed.
        raise NotImplementedError("Metadata-aware reranking is not implemented yet.")
