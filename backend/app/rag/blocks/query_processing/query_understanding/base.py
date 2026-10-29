"""Abstract class for Query Understanding."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import QueryAnalysis


class BaseQueryUnderstanding(PipelineBlock):
    """Analyse the question.

    Input:  the user's question
    Output: QueryAnalysis (intent, and FilterCriteria the question states — e.g. campus "ERICA").
            Its criteria are what Metadata Prefiltering and Postfiltering enforce.
    """

    @abstractmethod
    async def analyze(self, question: str) -> QueryAnalysis: ...
