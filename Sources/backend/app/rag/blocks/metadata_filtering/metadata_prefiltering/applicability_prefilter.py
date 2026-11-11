"""IMPLEMENTED — prefilter on the AAES chunk tags with the student's profile (R9-scope, R15)."""

from __future__ import annotations

from app.rag.aaes import prefilter_conditions
from app.rag.blocks.metadata_filtering.metadata_prefiltering.base import BaseMetadataPrefilter
from app.rag.schemas import FilterCriteria, RetrievalFilter


class ApplicabilityPrefilter(BaseMetadataPrefilter):
    """No hyperparameters. Needs a profile from query understanding (profile_understanding or self_query).

    Known values and the applicant scope default become a hard predicate on the app_* payload fields; a
    chunk that does not constrain an attribute stays eligible. This is the hard-filter baseline AAES is
    compared with: a wrong or missing value can remove the right evidence before ranking.
    """

    async def build_filter(self, criteria: FilterCriteria, profile: dict | None = None) -> RetrievalFilter | None:
        if not profile:
            return None
        return RetrievalFilter(conditions=prefilter_conditions(profile), include_unknown=True)
