"""Abstract class for Query Rewriting."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import RewrittenQuery


class BaseQueryRewriter(PipelineBlock):
    """Input: the question. Output: RewrittenQuery (the search query + optional alternatives).

    The ORIGINAL question is still used in the prompt; only retrieval uses the rewritten query.
    """

    @abstractmethod
    async def rewrite(self, question: str) -> RewrittenQuery: ...
