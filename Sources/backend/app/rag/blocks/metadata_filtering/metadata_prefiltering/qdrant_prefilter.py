"""IMPLEMENTED — turn the metadata criteria into a predicate that retrieval applies DURING the search."""

from __future__ import annotations

from app.rag.blocks.metadata_filtering.metadata_prefiltering.base import BaseMetadataPrefilter
from app.rag.schemas import FilterCriteria, RetrievalFilter


class QdrantMetadataPrefilter(BaseMetadataPrefilter):
    """Hyperparameters:
    include_unknown      a document that does not state the field (e.g. no campus) stays eligible
                         (unknown ≠ ineligible). Off = such documents are excluded.
    include_campus_wide  a document for every campus (campus: ALL) is eligible for any campus.

    Dense retrieval sends the predicate to Qdrant as a payload filter; BM25 applies the same predicate
    while ranking. Only eligible chunks are ranked, so Top K is filled with eligible chunks.
    """

    async def build_filter(self, criteria: FilterCriteria, profile: dict | None = None) -> RetrievalFilter | None:
        return criteria.to_filter(self.params["include_unknown"], "all" if self.params["include_campus_wide"] else None)
