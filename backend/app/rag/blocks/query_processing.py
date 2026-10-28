"""Blocks that work on the question before retrieval: understanding, rewriting,
constraint validation and metadata filtering. All four are FUTURE WORK (not implemented)."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.base import PipelineBlock
from app.rag.schemas import QueryAnalysis


# --------------------------------------------------------------------------- Query Understanding


class BaseQueryUnderstanding(PipelineBlock):
    """Find what the question is about.  Input: question.  Output: QueryAnalysis (e.g. constraints)."""

    @abstractmethod
    async def analyze(self, question: str) -> QueryAnalysis: ...


class RuleBasedQueryUnderstanding(BaseQueryUnderstanding):
    """PLANNED — detect campus / student type with simple keyword rules."""

    async def analyze(self, question: str) -> QueryAnalysis:
        # TODO:
        # 1. Look for words like "ERICA", "Seoul campus", "international student".
        # 2. Return QueryAnalysis(constraints={"campus": "ERICA", ...}).
        raise NotImplementedError("Query understanding is not implemented yet.")


# --------------------------------------------------------------------------- Query Rewriting


class BaseQueryRewriter(PipelineBlock):
    """Make the question a better search query.  Input: question.  Output: search query (str)."""

    @abstractmethod
    async def rewrite(self, question: str) -> str: ...


class LLMQueryRewriter(BaseQueryRewriter):
    """PLANNED — ask the LLM to rewrite the question into a clear search query."""

    async def rewrite(self, question: str) -> str:
        # TODO:
        # 1. Build a short prompt: "Rewrite this question as a search query: ...".
        # 2. Call the LLM (self.services.ollama).
        # 3. Return the rewritten text. The original question is still used for the answer.
        raise NotImplementedError("Query rewriting is not implemented yet.")


# --------------------------------------------------------------------------- Constraint Validation


class BaseConstraintValidator(PipelineBlock):
    """Check detected constraints.  Input: QueryAnalysis.  Output: allowed constraints (dict)."""

    @abstractmethod
    async def validate(self, analysis: QueryAnalysis) -> dict[str, str]: ...


class VocabularyConstraintValidator(BaseConstraintValidator):
    """PLANNED — keep only values from a fixed list (e.g. campus must be SEOUL or ERICA)."""

    async def validate(self, analysis: QueryAnalysis) -> dict[str, str]:
        # TODO: drop constraints whose values are not in an allowed list, and return the rest.
        raise NotImplementedError("Constraint validation is not implemented yet.")


# --------------------------------------------------------------------------- Metadata Filtering


class BaseMetadataFilter(PipelineBlock):
    """Decide which documents may be searched.

    Input:  validated constraints, e.g. {"campus": "ERICA"}
    Output: a filter {payload field: allowed values} for the retrievers, or None for no filter
    """

    @abstractmethod
    async def build_filter(self, constraints: dict[str, str]) -> dict[str, list[str]] | None: ...


class ExactMetadataFilter(BaseMetadataFilter):
    """PLANNED — only chunks whose metadata equals the constraint."""

    async def build_filter(self, constraints: dict[str, str]) -> dict[str, list[str]] | None:
        # TODO:
        # 1. Store the metadata field (e.g. campus) in the Qdrant payload during indexing.
        # 2. Return {"campus": ["ERICA", "ALL"]} so university-wide documents are kept.
        # 3. QdrantDenseRetriever already turns this into a Qdrant filter.
        raise NotImplementedError("Metadata filtering is not implemented yet.")
