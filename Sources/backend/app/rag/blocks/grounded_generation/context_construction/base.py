"""Abstract class for Context Construction."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import Evidence, PromptContext


class BaseContextBuilder(PipelineBlock):
    """Input: question + selected Evidence. Output: PromptContext (chat messages + labelled evidence).

    Each evidence block gets a label ("E1", "E2", …) so the answer can refer to its sources.
    """

    @abstractmethod
    async def build(self, question: str, evidence: list[Evidence]) -> PromptContext: ...
