"""IMPLEMENTED — Reciprocal Rank Fusion: merge rankings using only the ranks, not the scores."""

from __future__ import annotations

from app.rag.blocks.retrieval.hybrid_fusion.base import BaseHybridFusion
from app.rag.schemas import Candidate, RetrievalResult


def reciprocal_rank_fusion(rankings: dict[str, list[Candidate]], k: int, top_k: int) -> list[Candidate]:
    """RRF(chunk) = Σ over rankings that contain the chunk of 1 / (k + rank).

    `rankings` maps a name ("dense", "lexical", "query 2", …) to a ranked list (best first). A chunk
    found by several rankings appears once and collects one term per ranking. Only ranks are used,
    so cosine and BM25 scores never have to be compared. Ties: better best original rank, then chunk_id.
    Each fused candidate keeps its original ranks and scores in `scores` (e.g. "dense_rank": 3).
    """
    fused: dict[str, dict] = {}
    for name, ranking in rankings.items():
        for candidate in ranking:
            entry = fused.setdefault(candidate.chunk_id, {"candidate": candidate, "rrf": 0.0, "best_rank": candidate.rank, "scores": {}})
            entry["rrf"] += 1.0 / (k + candidate.rank)
            entry["best_rank"] = min(entry["best_rank"], candidate.rank)
            entry["scores"].update(candidate.scores)
            entry["scores"][f"{name}_rank"] = candidate.rank
    ordered = sorted(fused.values(), key=lambda e: (-e["rrf"], e["best_rank"], e["candidate"].chunk_id))[:top_k]
    return [e["candidate"].model_copy(update={"rank": i + 1, "score": round(e["rrf"], 6), "scores": {**e["scores"], "rrf": round(e["rrf"], 6)}})
            for i, e in enumerate(ordered)]  # fmt: skip


class ReciprocalRankFusion(BaseHybridFusion):
    """Hyperparameters: rrf_k (60 = the value from the original RRF paper), top_k (merged list length).
    The depth of each input list is the Top K of that retriever."""

    async def fuse(self, dense: RetrievalResult, lexical: RetrievalResult) -> RetrievalResult:
        candidates = reciprocal_rank_fusion({"dense": dense.candidates, "lexical": lexical.candidates}, self.params["rrf_k"], self.params["top_k"])
        found_by = {"both": 0, "dense only": 0, "lexical only": 0}
        for c in candidates:
            found_by["both" if "dense_rank" in c.scores and "lexical_rank" in c.scores else
                     "dense only" if "dense_rank" in c.scores else "lexical only"] += 1  # fmt: skip
        details = {"score": "RRF (sum of 1/(k + rank))", "rrf_k": self.params["rrf_k"], "dense_in": len(dense.candidates),
                   "lexical_in": len(lexical.candidates), "found_by": found_by}  # fmt: skip
        return RetrievalResult(candidates=candidates, applied_filter=dense.applied_filter or lexical.applied_filter, details=details)
