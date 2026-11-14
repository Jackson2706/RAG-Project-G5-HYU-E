"""IMPLEMENTED — AAES steps 3 and 4: branches with information gain, then the action policy."""

from __future__ import annotations

from app.rag.aaes import branch_note, decide, extract_profile, render_action
from app.rag.applicability import VOCABULARY, ChunkCondition
from app.rag.blocks.evidence.evidence_sufficiency.base import BaseSufficiencyChecker
from app.rag.schemas import Evidence, SufficiencyDecision
from app.rag.text import query_coverage

UNTAGGED = ChunkCondition(campus=list(VOCABULARY["campus"])).to_dict()  # never used on a tagged index


class ApplicabilitySufficiency(BaseSufficiencyChecker):
    """Hyperparameters: relevance_threshold (query coverage a chunk needs to count as relevant), max_branches
    (more → CLARIFY), temporal (drop outdated support when a newer version exists; off = A6) and policy
    ("aaes", "always_clarify" = A3, or "question_only" = A4).

    Proceeds (generation runs) for ANSWER and CONDITIONAL; CLARIFY, ABSTAIN and CONFIRM get a fixed reply.
    """

    async def check(self, question: str, evidence: list[Evidence], profile: dict | None = None) -> SufficiencyDecision:
        profile = profile or extract_profile(question)
        coverage, chunks = self.relevant_chunks(question, evidence)
        d = decide(chunks, profile, max_branches=self.params["max_branches"], temporal=self.params["temporal"], policy=self.params["policy"],
                     question=question)
        return self.result(d, evidence, profile, coverage)

    def relevant_chunks(self, question: str, evidence: list[Evidence]) -> tuple[dict[str, float], list[dict]]:
        """(query coverage per chunk, the relevant chunks in the form decide() reads)."""
        coverage = {e.chunk_id: round(query_coverage(question, e.text), 4) for e in evidence}
        relevant = [e for e in evidence if coverage[e.chunk_id] >= self.params["relevance_threshold"]]
        chunks = [{"id": e.chunk_id, "doc_id": e.doc_id, "condition": e.applicability.get("condition") or UNTAGGED,
                   "status": e.applicability.get("condition_status") or "unknown", "superseded": e.applicability.get("superseded", False)}
                  for e in relevant]  # fmt: skip
        return coverage, chunks

    def result(self, d: dict, evidence: list[Evidence], profile: dict, coverage: dict[str, float]) -> SufficiencyDecision:
        action = d["action"]
        support = [e.chunk_id for e in evidence if e.chunk_id in set(d["support"])]
        proceed = action in ("ANSWER", "CONDITIONAL")
        return SufficiencyDecision(sufficient=proceed, reason=f"{action}: {d['reason']}", action=action,
                                   signals={**d, "coverage": coverage, "relevance_threshold": self.params.get("relevance_threshold")},
                                   evidence_ids=support if proceed else None, message=None if proceed else render_action(d, profile),
                                   prompt_note=branch_note(d, support) if action == "CONDITIONAL" else None)  # fmt: skip
