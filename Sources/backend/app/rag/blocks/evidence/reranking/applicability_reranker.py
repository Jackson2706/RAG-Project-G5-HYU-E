"""IMPLEMENTED — AAES step 2: cross-encoder relevance, then a soft penalty for evidence that does not apply."""

from __future__ import annotations

from app.rag.aaes import extract_profile, known_values, label_chunk, penalized_score
from app.rag.blocks.evidence.reranking.cross_encoder import CrossEncoderReranker
from app.rag.schemas import Evidence


class ApplicabilityReranker(CrossEncoderReranker):
    """Hyperparameters: the cross-encoder's, plus lam (penalty for conflicting), mu (penalty for outdated)
    and hard_filter (A1: drop conflicting evidence instead).

    Each chunk gets an applicability label (compatible / conflicting / open / unconditioned / unknown) for
    the student's profile. Relevance (eligibility-blind) and eligibility stay separate: the penalty
    moves an ineligible chunk down, it does not remove it. Scores are cross-encoder logits, so λ and μ
    are in logit units (tuned on dev only).
    """

    async def rerank(self, query: str, evidence: list[Evidence], profile: dict | None = None) -> list[Evidence]:
        ranked = await super().rerank(query, evidence)
        depth = self.params["rerank_depth"]
        head, tail = ranked[:depth], ranked[depth:]
        known = known_values(profile or extract_profile(query))
        scores, labelled = {}, []
        for e in head:
            app = e.applicability
            label = label_chunk(app["condition"], app.get("condition_status"), known) if app.get("condition") else "unknown"
            if self.params["hard_filter"] and label == "conflicting":
                continue
            scores[e.chunk_id] = penalized_score(e.score, label, app.get("superseded", False), self.params["lam"], self.params["mu"])
            labelled.append(e.model_copy(update={"applicability": {**app, "label": label}}))
        labelled.sort(key=lambda e: -scores[e.chunk_id])  # stable: ties keep the cross-encoder order
        self.trace_details = {"labels": {e.chunk_id: e.applicability["label"] for e in labelled},
                              "dropped_conflicting": len(head) - len(labelled)}  # fmt: skip
        return self.reordered(labelled, tail, scores, "applicability")
