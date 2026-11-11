"""IMPLEMENTED — AAES step 1: the student's profile from the question and the earlier turns (rules, no LLM)."""

from __future__ import annotations

from app.rag.aaes import extract_profile
from app.rag.blocks.query_processing.query_understanding.base import BaseQueryUnderstanding
from app.rag.schemas import QueryAnalysis


class ProfileUnderstanding(BaseQueryUnderstanding):
    """Each vocabulary attribute gets values and a status: stated, remembered (an earlier turn), stale,
    scope_default (not an applicant unless said, A17) or missing. Nothing is guessed (aaes_spec.md, step 1)."""

    async def analyze(self, question: str, history: list[str] | tuple = ()) -> QueryAnalysis:
        return QueryAnalysis(profile=extract_profile(question, history))
