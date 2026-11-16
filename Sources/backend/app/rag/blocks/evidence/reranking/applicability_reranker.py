"""IMPLEMENTED — AAES step 2: cross-encoder relevance, then a soft penalty for evidence that does not apply.

mode (AAES+, deck v4 Task 4): rules = labels from the chunk tags (condition_fit, AAES today); llm = one batched LLM
call over the top `llm_depth` passages after the cross-encoder gives each a label (everyone / this student / other
students / depends) and a relevance flag, which replaces the word-overlap relevance rule in step 3; both = tag labels
where tags exist, the LLM label only for passages whose tag label is "unknown", and a passage counts as relevant if
either the overlap rule or the LLM says so. An invalid LLM item is "unknown" in llm mode and keeps its tag label in both.
"""

from __future__ import annotations

from app.rag import aaes_llm
from app.rag.aaes import extract_profile, known_values, label_chunk, penalized_score
from app.rag.blocks.evidence.reranking.cross_encoder import CrossEncoderReranker
from app.rag.schemas import Evidence


class ApplicabilityReranker(CrossEncoderReranker):
    """Hyperparameters: the cross-encoder's, plus lam (penalty for conflicting), mu (penalty for outdated),
    hard_filter (A1: drop conflicting evidence instead), and for AAES+ mode, llm_depth and the auxiliary LLM's settings.

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
        labels = {e.chunk_id: label_chunk(e.applicability["condition"], e.applicability.get("condition_status"), known)
                  if e.applicability.get("condition") else "unknown" for e in head}  # fmt: skip
        mode = self.params.get("mode", "rules")
        llm = await self._llm_labels(query, head, known, labels) if mode != "rules" else {}
        scores, labelled = {}, []
        for e in head:
            app = dict(e.applicability)
            if e.chunk_id in llm:
                labels[e.chunk_id] = llm[e.chunk_id]["label"]
                app.update({"llm_label": llm[e.chunk_id]["label"], "llm_relevant": llm[e.chunk_id]["relevant"],
                            "llm_depends_on": llm[e.chunk_id]["depends_on"]})  # fmt: skip
            if mode != "rules":
                app["relevance_mode"] = mode
            label = labels[e.chunk_id]
            if self.params["hard_filter"] and label == "conflicting":
                continue
            scores[e.chunk_id] = penalized_score(e.score, label, app.get("superseded", False), self.params["lam"], self.params["mu"])
            labelled.append(e.model_copy(update={"applicability": {**app, "label": label}}))
        labelled.sort(key=lambda e: -scores[e.chunk_id])  # stable: ties keep the cross-encoder order
        self.trace_details.update({"labels": {e.chunk_id: e.applicability["label"] for e in labelled},
                                   "dropped_conflicting": len(head) - len(labelled)})  # fmt: skip
        return self.reordered(labelled, tail, scores, "applicability")

    async def _llm_labels(self, query: str, head: list[Evidence], known: dict, labels: dict) -> dict[str, dict]:
        top = head[: self.params.get("llm_depth", 6)]
        if self.params["mode"] == "both":
            top = [e for e in top if labels[e.chunk_id] == "unknown"]
        if not top:
            return {}
        ids = {f"P{i}": e for i, e in enumerate(top, 1)}
        student = "; ".join(f"{a}: {', '.join(v)}" for a, v in known.items()) or "nothing known"
        user = f"Question: {query}\nKnown about the student: {student}\n\n" + "\n\n".join(f"[{pid}]\n{e.text[:1200]}" for pid, e in ids.items())
        parsed, rejected = aaes_llm.parse_applies(await aaes_llm.call(self, aaes_llm.APPLIES, user), {p: e.text for p, e in ids.items()}, known)
        aaes_llm.fallback(self, "applies", rejected + [f"{p}:missing" for p in ids if p not in parsed and "unparseable" not in rejected])
        if self.params["mode"] == "llm":  # spec: an invalid item is "unknown"; its relevance falls back to the overlap rule
            parsed |= {p: {"relevant": None, "label": "unknown", "depends_on": []} for p in ids if p not in parsed}
        out = {ids[p].chunk_id: v for p, v in parsed.items()}
        self.trace_details["llm_labels"] = out
        return out
