"""Abstract class for Hybrid Fusion (hybrid retrieval)."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import RetrievalResult


class BaseHybridFusion(PipelineBlock):
    """Input: the dense and the lexical RetrievalResult. Output: one merged RetrievalResult.

    Both inputs were already searched with the same prefilter predicate, so fusion never
    re-introduces ineligible chunks.
    """

    @abstractmethod
    async def fuse(self, dense: RetrievalResult, lexical: RetrievalResult) -> RetrievalResult: ...
