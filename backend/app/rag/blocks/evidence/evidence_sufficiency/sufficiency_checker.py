"""PLANNED — sufficient only if the best similarity score reaches `min_score`."""

from __future__ import annotations

from app.rag.blocks.evidence.evidence_sufficiency.base import BaseSufficiencyChecker
from app.rag.schemas import Evidence, SufficiencyDecision


class ScoreThresholdChecker(BaseSufficiencyChecker):
    async def check(self, question: str, evidence: list[Evidence]) -> SufficiencyDecision:
        # TODO:
        # 1. best = max(e.score for e in evidence)
        # 2. Return SufficiencyDecision(sufficient=best >= self.params["min_score"], reason=f"best score {best}")
        # 3. Choose min_score by measuring it on data/eval/sample_questions.jsonl — never guess it.
        raise NotImplementedError("Evidence sufficiency is not implemented yet.")
