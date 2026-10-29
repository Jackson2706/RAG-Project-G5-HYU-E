"""Abstract class for Reranking."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import Evidence


class BaseReranker(PipelineBlock):
    """Reorder evidence by relevance.

    Input:  the query and the Evidence list (with text)
    Output: the same Evidence objects in a new order (renumber `rank` from 1)
    """

    @abstractmethod
    async def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]: ...
