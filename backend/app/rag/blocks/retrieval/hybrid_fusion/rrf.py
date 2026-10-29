"""PLANNED — Reciprocal Rank Fusion: score = Σ 1 / (rrf_k + rank) over both lists."""

from __future__ import annotations

from app.rag.blocks.retrieval.hybrid_fusion.base import BaseHybridFusion
from app.rag.schemas import RetrievalResult


class ReciprocalRankFusion(BaseHybridFusion):
    async def fuse(self, dense: RetrievalResult, lexical: RetrievalResult) -> RetrievalResult:
        # TODO:
        # 1. For every chunk_id, add 1 / (self.params["rrf_k"] + rank) for each list it appears in.
        # 2. Sort by that score, keep self.params["top_k"], and renumber `rank` from 1.
        # 3. Return RetrievalResult(candidates=..., applied_filter=dense.applied_filter).
        raise NotImplementedError("Hybrid fusion is not implemented yet.")
