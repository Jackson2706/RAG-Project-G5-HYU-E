"""PLANNED — a model that reads question and chunk *together* scores each pair."""

from __future__ import annotations

from app.rag.blocks.evidence.reranking.base import BaseReranker
from app.rag.schemas import Evidence


class CrossEncoderReranker(BaseReranker):
    async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]:
        # TODO:
        # 1. Load a cross-encoder: sentence_transformers.CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2").
        # 2. Score each pair: model.predict([(query, e.text) for e in evidence]).
        # 3. Sort by score (highest first), keep self.params["top_n"], renumber rank (e.model_copy(update=...)).
        raise NotImplementedError("Cross-encoder reranking is not implemented yet.")
