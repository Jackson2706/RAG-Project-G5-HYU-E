"""PLANNED — build a predicate on Qdrant payload fields (campus, audience, …)."""

from __future__ import annotations

from app.rag.blocks.metadata_filtering.metadata_prefiltering.base import BaseMetadataPrefilter
from app.rag.schemas import FilterCriteria, RetrievalFilter


class QdrantMetadataPrefilter(BaseMetadataPrefilter):
    async def build_filter(self, criteria: FilterCriteria) -> RetrievalFilter | None:
        # TODO:
        # 1. Make sure the fields exist in the Qdrant payload: add them in
        #    ingestion/vector_indexing/qdrant_indexer.py (from document metadata), then re-index.
        # 2. For each condition in criteria.conditions(), allow the value AND university-wide documents,
        #    e.g. {"campus": [criteria.campus, "ALL"]}.
        # 3. Return RetrievalFilter(conditions=..., include_unknown=True), or None if criteria is empty.
        #    QdrantDenseRetriever already applies RetrievalFilter inside the Qdrant search.
        raise NotImplementedError("Metadata prefiltering is not implemented yet.")
