"""IMPLEMENTED — keep evidence in rank order within a token budget."""

from __future__ import annotations

from app.rag.blocks.evidence.evidence_selection.base import BaseEvidenceSelector
from app.rag.schemas import Evidence


class TokenBudgetSelector(BaseEvidenceSelector):
    """Keep evidence in rank order until `max_evidence_tokens` would be exceeded (the first chunk is
    always kept). Token counts were measured during ingestion.
    deduplicate: skip a chunk whose text is identical to an already selected one (it would only spend budget).
    Ordering policy: rank order only — a smaller chunk further down never jumps ahead.
    """

    async def select(self, evidence: list[Evidence]) -> list[Evidence]:
        budget = self.params["max_evidence_tokens"]
        selected, used, seen = [], 0, set()
        for item in evidence:
            if self.params["deduplicate"] and item.text.strip() in seen:
                continue
            if selected and used + item.token_count > budget:
                break
            selected.append(item)
            seen.add(item.text.strip())
            used += item.token_count
        return selected
