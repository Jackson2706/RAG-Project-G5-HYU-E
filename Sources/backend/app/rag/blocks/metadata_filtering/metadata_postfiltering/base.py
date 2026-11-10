"""Abstract class for Metadata Postfiltering.

POSTFILTERING removes ineligible candidates from an already retrieved candidate list. It cannot
bring back eligible chunks that never entered that list (candidate starvation). Compare
PREFILTERING (metadata_filtering/metadata_prefiltering/), which restricts the search itself.
"""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import Candidate, FilterCriteria, PostfilterResult


class BaseMetadataPostfilter(PipelineBlock):
    """Keep only eligible candidates.

    Input:  the retrieved Candidates and the validated FilterCriteria
    Output: PostfilterResult (kept candidates + removed candidates with reasons). It may be empty —
            never relax mandatory conditions to fill it.
    """

    @abstractmethod
    async def filter_candidates(self, candidates: list[Candidate], criteria: FilterCriteria) -> PostfilterResult: ...
