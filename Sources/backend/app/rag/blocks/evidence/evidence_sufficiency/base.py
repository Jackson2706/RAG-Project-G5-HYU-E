"""Abstract class for Evidence Sufficiency."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import Evidence, SufficiencyDecision


class BaseSufficiencyChecker(PipelineBlock):
    """Decide whether the selected evidence can answer the question.

    Input:  question, selected Evidence
    Output: SufficiencyDecision(sufficient, reason). If not sufficient, the pipeline abstains:
            generation is not called and the user gets the "not enough information" answer.
    """

    @abstractmethod
    async def check(self, question: str, evidence: list[Evidence]) -> SufficiencyDecision: ...
