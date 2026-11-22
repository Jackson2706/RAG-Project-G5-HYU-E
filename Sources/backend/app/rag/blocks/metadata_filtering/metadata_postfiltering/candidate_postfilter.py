"""IMPLEMENTED — remove ineligible candidates from the already retrieved list."""

from __future__ import annotations

from app.rag.blocks.metadata_filtering.metadata_postfiltering.base import BaseMetadataPostfilter
from app.rag.schemas import Candidate, FilterCriteria, PostfilterResult, RemovedCandidate


class CandidateMetadataPostfilter(BaseMetadataPostfilter):
    """Hyperparameters: include_unknown, include_campus_wide (the same meaning as for prefiltering, so
    both placements can use the identical predicate).

    Each candidate's document metadata is read from MongoDB and checked; removed candidates are
    listed with the reason. Nothing is retrieved again: if few eligible chunks were among the
    retrieved ones, the list simply gets shorter (candidate starvation) — reported in `details`.
    """

    async def filter_candidates(self, candidates: list[Candidate], criteria: FilterCriteria) -> PostfilterResult:
        predicate = criteria.to_filter(self.params["include_unknown"], "all" if self.params["include_campus_wide"] else None)
        if predicate is None:
            return PostfilterResult(kept=candidates, details={"received": len(candidates), "kept": len(candidates), "predicate": None})
        documents = self.services.db.get_documents(list({c.doc_id for c in candidates}))
        kept, removed = [], []
        for c in candidates:
            reason = predicate.explain(documents.get(c.doc_id, {}).get("metadata", {}))
            if reason is None:
                kept.append(c.model_copy(update={"rank": len(kept) + 1, "scores": {**c.scores, "rank_before": c.rank}}))
            else:
                removed.append(RemovedCandidate(chunk_id=c.chunk_id, reason=reason))
        details = {"received": len(candidates), "kept": len(kept), "removed": len(removed), "predicate": predicate.model_dump(),
                   "starved": len(kept) < len(candidates), "empty": not kept}  # fmt: skip
        return PostfilterResult(kept=kept, removed=removed, details=details)
