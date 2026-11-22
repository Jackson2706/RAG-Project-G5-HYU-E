"""Abstract class for Evidence Selection."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import Evidence


class BaseEvidenceSelector(PipelineBlock):
    """Input: Evidence list (best first). Output: the Evidence to put in the prompt."""

    @abstractmethod
    async def select(self, evidence: list[Evidence]) -> list[Evidence]: ...
