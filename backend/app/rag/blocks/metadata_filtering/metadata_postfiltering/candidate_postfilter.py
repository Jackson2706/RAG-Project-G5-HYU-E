"""PLANNED — check each retrieved candidate's document metadata against the criteria."""

from __future__ import annotations

from app.rag.blocks.metadata_filtering.metadata_postfiltering.base import BaseMetadataPostfilter
from app.rag.schemas import Candidate, FilterCriteria, PostfilterResult


class CandidateMetadataPostfilter(BaseMetadataPostfilter):
    async def filter_candidates(self, candidates: list[Candidate], criteria: FilterCriteria) -> PostfilterResult:
        # TODO:
        # 1. If criteria.conditions() is empty, keep every candidate.
        # 2. Load each candidate's document: self.services.db.get_documents([c.doc_id for c in candidates]).
        # 3. Compare document["metadata"] with each condition ("ALL" = university-wide; decide how to
        #    treat a missing field and say so in `reason`).
        # 4. Return PostfilterResult(kept=[...], removed=[RemovedCandidate(chunk_id=..., reason=...)]).
        raise NotImplementedError("Metadata postfiltering is not implemented yet.")
