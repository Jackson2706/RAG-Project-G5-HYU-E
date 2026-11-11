"""IMPLEMENTED — query-term coverage reranking (the Lesson 5 lab method, "query-term-coverage-v1")."""

from __future__ import annotations

from app.rag.blocks.evidence.reranking.base import BaseReranker
from app.rag.schemas import Evidence
from app.rag.text import query_coverage


class CoverageReranker(BaseReranker):
    """Sort by the fraction of the query's content terms that occur in the chunk (highest first).

    Ties: higher incoming score first (the score of the ranking it received), then better incoming rank.
    A cheap, fully explainable baseline. Coverage counts shared words; it does not prove the chunk
    answers the question (that is Evidence Sufficiency's job, and even that is only a heuristic).
    """

    async def rerank(self, query: str, evidence: list[Evidence], profile: dict | None = None) -> list[Evidence]:
        depth = self.params["rerank_depth"]
        head, tail = evidence[:depth], evidence[depth:]
        coverage = {e.chunk_id: query_coverage(query, e.text) for e in head}
        head = sorted(head, key=lambda e: (-coverage[e.chunk_id], -e.score, e.rank))
        return self.reordered(head, tail, coverage, "coverage")
