"""PLANNED — let the LLM read the question and fill in the metadata criteria it states."""

from __future__ import annotations

from app.rag.blocks.query_processing.query_understanding.base import BaseQueryUnderstanding
from app.rag.schemas import QueryAnalysis


class LLMQueryUnderstanding(BaseQueryUnderstanding):
    async def analyze(self, question: str) -> QueryAnalysis:
        # TODO:
        # 1. Ask the LLM (self.services.ollama) for JSON: {"intent": ..., "campus": ..., "audience": ...}.
        # 2. Keep only values from allowed lists (e.g. campus in {"SEOUL", "ERICA"}); drop anything else.
        # 3. Return QueryAnalysis(intent=..., criteria=FilterCriteria(...)). Never invent a value the
        #    question does not state.
        raise NotImplementedError("Query understanding is not implemented yet.")
