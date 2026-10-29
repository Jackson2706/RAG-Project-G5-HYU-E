"""PLANNED — Okapi BM25 keyword ranking."""

from __future__ import annotations

from app.rag.blocks.retrieval.lexical_retrieval.base import BaseLexicalRetriever
from app.rag.schemas import RetrievalFilter, RetrievalResult


class BM25Retriever(BaseLexicalRetriever):
    async def retrieve(self, query: str, prefilter: RetrievalFilter | None = None) -> RetrievalResult:
        # TODO (step-by-step tutorial: docs/05_ADD_NEW_METHOD.md):
        # 1. Load all chunk texts: self.services.db.chunks.find({}, {"chunk_id": 1, "doc_id": 1, "text": 1})
        # 2. Split texts and query into lowercase words.
        # 3. Score each chunk with BM25 (self.params["k1"], self.params["b"]).
        # 4. Return the top self.params["top_k"] as Candidates, best first.
        raise NotImplementedError("BM25 retrieval is not implemented yet.")
