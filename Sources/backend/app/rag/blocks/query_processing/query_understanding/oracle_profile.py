"""IMPLEMENTED (ablation A2) — AAES step 1 replaced by the labeled profile: what the student really stated."""

from __future__ import annotations

from app.rag.aaes import extract_profile
from app.rag.blocks.query_processing.query_understanding.base import BaseQueryUnderstanding
from app.rag.schemas import QueryAnalysis


class OracleProfileUnderstanding(BaseQueryUnderstanding):
    """The case's labeled `stated_profile` (latest values, GUIDELINES 11.7) as "stated" facts; scope defaults as in
    step 1. Unstated attributes stay missing, so A2 measures AAES with perfect profile extraction, not with the
    hidden gold profile. Needs a labeled case: the runner or a demo case sets `self.oracle`."""

    needs_oracle = "profile"
    oracle: dict = {}

    async def analyze(self, question: str, history: list[str] | tuple = ()) -> QueryAnalysis:
        stated = {a: {"values": [v], "status": "stated", "evidence": "labeled case"} for a, v in self.oracle["profile"].items()}
        return QueryAnalysis(profile=extract_profile("", (), remembered=stated))
