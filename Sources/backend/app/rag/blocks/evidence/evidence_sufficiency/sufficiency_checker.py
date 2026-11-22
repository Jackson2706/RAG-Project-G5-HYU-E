"""IMPLEMENTED — a simple threshold gate: proceed when the evidence signal reaches a threshold, else abstain."""

from __future__ import annotations

from app.rag.blocks.evidence.evidence_sufficiency.base import BaseSufficiencyChecker
from app.rag.schemas import Evidence, SufficiencyDecision
from app.rag.text import query_coverage


class ScoreThresholdChecker(BaseSufficiencyChecker):
    """Hyperparameters:
    signal             "query_coverage": best share of question words found in a selected chunk
                       (Lesson 5's gate signal, 0–1); "dense_similarity": best cosine similarity
                       from dense retrieval among the selected chunks.
    threshold          proceed when signal ≥ threshold (Lesson 5's fixed instructor value: 0.30 coverage).
    on_missing_signal  what to do when the signal cannot be measured (e.g. dense_similarity without
                       dense retrieval): "abstain" or "proceed".

    A HEURISTIC: a high score means "looks related", not "proves the answer is supported".
    No evidence at all always abstains.
    """

    async def check(self, question: str, evidence: list[Evidence], profile: dict | None = None) -> SufficiencyDecision:
        signal, threshold = self.params["signal"], self.params["threshold"]
        if not evidence:
            return SufficiencyDecision(sufficient=False, reason="no evidence was selected", signals={"evidence": 0})
        if signal == "query_coverage":
            values = [query_coverage(question, e.text) for e in evidence]
        else:
            values = [e.scores["dense"] for e in evidence if "dense" in e.scores]
        if not values:
            proceed = self.params["on_missing_signal"] == "proceed"
            return SufficiencyDecision(sufficient=proceed, reason=f"{signal} could not be measured; policy: {self.params['on_missing_signal']}",
                                       signals={"signal": signal, "observed": None, "threshold": threshold})  # fmt: skip
        observed = max(values)
        ok = observed >= threshold
        reason = f"best {signal} {observed:.3f} {'≥' if ok else '<'} threshold {threshold:.3f}"
        return SufficiencyDecision(sufficient=ok, reason=reason, signals={"signal": signal, "observed": round(observed, 4),
                                                                           "threshold": threshold, "evidence": len(evidence)})  # fmt: skip
