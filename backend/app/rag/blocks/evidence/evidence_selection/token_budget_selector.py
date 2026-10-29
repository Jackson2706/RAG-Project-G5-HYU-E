"""IMPLEMENTED — keep evidence in rank order within a token budget."""

from __future__ import annotations

from app.rag.blocks.evidence.evidence_selection.base import BaseEvidenceSelector
from app.rag.schemas import Evidence


class TokenBudgetSelector(BaseEvidenceSelector):
    """Keep evidence until `max_evidence_tokens` would be exceeded (the first chunk is always kept).
    Token counts were measured during ingestion."""

    async def select(self, evidence: list[Evidence]) -> list[Evidence]:
        budget = self.params["max_evidence_tokens"]
        selected, used = [], 0
        for item in evidence:
            if selected and used + item.token_count > budget:
                break
            selected.append(item)
            used += item.token_count
        return selected
