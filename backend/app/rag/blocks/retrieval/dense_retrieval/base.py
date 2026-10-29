"""Abstract class for Dense Retrieval."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import RetrievalFilter, RetrievalResult


class BaseDenseRetriever(PipelineBlock):
    """Find chunks whose *meaning* is close to the query.

    Input:  query text; optional RetrievalFilter from metadata prefiltering, which MUST be applied
            during the search (only eligible chunks may be ranked)
    Output: RetrievalResult with Candidates (rank, chunk_id, doc_id, score), best first, and the
            filter that was really applied. Hyperparameters such as top_k are in self.params.
    """

    @abstractmethod
    async def retrieve(self, query: str, prefilter: RetrievalFilter | None = None) -> RetrievalResult: ...
