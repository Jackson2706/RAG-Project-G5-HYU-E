"""IMPLEMENTED — the metadata criteria the student states explicitly (set in the Configuration tab)."""

from __future__ import annotations

from app.rag.blocks.query_processing.query_understanding.base import BaseQueryUnderstanding
from app.rag.schemas import FilterCriteria, QueryAnalysis


class StatedCriteria(BaseQueryUnderstanding):
    """Hyperparameters: the FilterCriteria fields (empty = no condition; comma-separated values = OR).

    No LLM and no guessing: the criteria are exactly what the user set, e.g. "I am an ERICA student".
    Metadata Prefiltering and Postfiltering both read these criteria, so they enforce the same predicate.
    """

    async def analyze(self, question: str) -> QueryAnalysis:
        values = {field: str(self.params.get(field, "")).strip() or None for field in FilterCriteria.model_fields}
        return QueryAnalysis(intent=None, criteria=FilterCriteria(**values))
