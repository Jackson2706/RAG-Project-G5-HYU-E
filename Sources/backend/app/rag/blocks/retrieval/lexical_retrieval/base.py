"""Abstract class for Lexical Retrieval."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import RetrievalFilter, RetrievalResult


class BaseLexicalRetriever(PipelineBlock):
    """Find chunks that share *words* with the query. Same input and output as BaseDenseRetriever,
    including the rule that a prefilter predicate must be applied while searching."""

    @abstractmethod
    async def retrieve(self, query: str, prefilter: RetrievalFilter | None = None) -> RetrievalResult: ...
