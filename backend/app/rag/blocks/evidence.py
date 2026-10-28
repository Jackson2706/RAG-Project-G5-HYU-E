"""Evidence blocks: choose which evidence goes to the LLM, and decide whether it is enough.

    Evidence Selection   BaseEvidenceSelector → TokenBudgetSelector (IMPLEMENTED)
    Sufficiency Gate     BaseSufficiencyGate  → ScoreThresholdGate (PLANNED)
"""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.base import PipelineBlock
from app.rag.schemas import Evidence, SufficiencyDecision


class BaseEvidenceSelector(PipelineBlock):
    """Pick the evidence for the prompt.  Input: Evidence list (best first).  Output: a shorter Evidence list."""

    @abstractmethod
    async def select(self, evidence: list[Evidence]) -> list[Evidence]: ...


class TokenBudgetSelector(BaseEvidenceSelector):
    """IMPLEMENTED — keep evidence in rank order until `max_evidence_tokens` would be exceeded
    (the first chunk is always kept). Token counts were measured during ingestion."""

    async def select(self, evidence: list[Evidence]) -> list[Evidence]:
        budget = self.params["max_evidence_tokens"]
        selected, used = [], 0
        for item in evidence:
            if selected and used + item.token_count > budget:
                break
            selected.append(item)
            used += item.token_count
        return selected


class BaseSufficiencyGate(PipelineBlock):
    """Decide whether the evidence can answer the question.

    Input:  question, selected Evidence
    Output: SufficiencyDecision(sufficient, reason). If not sufficient, the LLM is not called.
    """

    @abstractmethod
    async def check(self, question: str, evidence: list[Evidence]) -> SufficiencyDecision: ...


class ScoreThresholdGate(BaseSufficiencyGate):
    """PLANNED — sufficient only if the best similarity score reaches `min_score`."""

    async def check(self, question: str, evidence: list[Evidence]) -> SufficiencyDecision:
        # TODO:
        # 1. best = max(e.score for e in evidence)
        # 2. Return SufficiencyDecision(best >= self.params["min_score"], f"best score {best}")
        # 3. Choose min_score by measuring it on data/eval/sample_questions.jsonl — never guess it.
        raise NotImplementedError("The evidence sufficiency check is not implemented yet.")
