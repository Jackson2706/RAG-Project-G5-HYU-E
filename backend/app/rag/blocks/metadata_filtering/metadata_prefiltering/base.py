"""Abstract class for Metadata Prefiltering.

PREFILTERING applies eligibility conditions during candidate retrieval: the retriever searches only
within the eligible subset. Compare POSTFILTERING (metadata_filtering/metadata_postfiltering/), which removes
ineligible candidates from an already retrieved list.
"""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import FilterCriteria, RetrievalFilter


class BaseMetadataPrefilter(PipelineBlock):
    """Turn validated metadata criteria into a retrieval predicate.

    Input:  FilterCriteria (from Query Understanding; empty if nothing was stated)
    Output: RetrievalFilter ({payload field: allowed values}) that the retrievers apply while
            searching, or None when there is nothing to filter.

    Do NOT retrieve and then filter here — that would be postfiltering.
    """

    @abstractmethod
    async def build_filter(self, criteria: FilterCriteria) -> RetrievalFilter | None: ...
