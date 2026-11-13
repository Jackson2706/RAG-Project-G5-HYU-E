"""IMPLEMENTED (bracket G1) — the labeled gold evidence replaces the retrieved evidence."""

from __future__ import annotations

from app.rag.blocks.evidence.evidence_selection.base import BaseEvidenceSelector
from app.rag.schemas import Evidence


class OracleEvidenceSelector(BaseEvidenceSelector):
    """Ignores the retrieved list and returns the case's gold spans as evidence: the upper bracket (perfect
    retrieval and selection). Needs a labeled case: the runner or a demo case sets `self.oracle`."""

    needs_oracle = "evidence"
    oracle: dict = {}

    async def select(self, evidence: list[Evidence]) -> list[Evidence]:
        return [Evidence(**e) for e in self.oracle["evidence"]]
