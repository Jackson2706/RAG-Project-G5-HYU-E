"""IMPLEMENTED (baseline) — keep the K best-ranked evidence items."""

from __future__ import annotations

from app.rag.blocks.evidence.evidence_selection.base import BaseEvidenceSelector
from app.rag.schemas import Evidence


class TopKSelector(BaseEvidenceSelector):
    """Keep the first `top_k` evidence items. The list is already best first (retrieval or
    reranking order), so this keeps the K most relevant chunks and drops the rest."""

    async def select(self, evidence: list[Evidence]) -> list[Evidence]:
        return evidence[: self.params["top_k"]]
