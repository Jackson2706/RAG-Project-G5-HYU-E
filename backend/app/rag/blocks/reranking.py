"""Block: Reranking — put the best evidence first. FUTURE WORK (not implemented)."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.base import PipelineBlock
from app.rag.schemas import Evidence


class BaseReranker(PipelineBlock):
    """Reorder evidence by relevance.

    Input:  the query and the Evidence list (with text)
    Output: the same Evidence objects in a new order (renumber `rank` from 1)
    """

    @abstractmethod
    async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]: ...


class CrossEncoderReranker(BaseReranker):
    """PLANNED — a model that reads question and chunk *together* scores each pair."""

    async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]:
        # TODO:
        # 1. Load a cross-encoder: sentence_transformers.CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2").
        # 2. Score each pair: model.predict([(query, e.text) for e in evidence]).
        # 3. Sort evidence by score (highest first), keep self.params["top_n"], renumber rank.
        raise NotImplementedError("Cross-encoder reranking is not implemented yet.")


class MetadataAwareReranker(BaseReranker):
    """PLANNED — move evidence that matches the student's situation (campus, year) up."""

    async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]:
        # TODO: add a bonus to the score of evidence whose document metadata matches the question.
        raise NotImplementedError("Metadata-aware reranking is not implemented yet.")
