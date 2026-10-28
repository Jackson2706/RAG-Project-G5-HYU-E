"""Retrieval blocks: find candidate chunks, combine candidate lists, load their text.

    Dense Retrieval       BaseDenseRetriever    → QdrantDenseRetriever (IMPLEMENTED)
    Lexical Retrieval     BaseLexicalRetriever  → BM25Retriever (PLANNED)
    Hybrid Fusion         BaseHybridFusion      → ReciprocalRankFusion (PLANNED)
    Metadata Enrichment   BaseMetadataEnricher  → MongoChunkLookup (IMPLEMENTED)

Every retriever returns the same RetrievalResult, so any of them can be used by the next stages.
"""

from __future__ import annotations

from abc import abstractmethod

from qdrant_client import models

from app.rag.blocks.base import PipelineBlock
from app.rag.schemas import Candidate, Evidence, RetrievalResult

# --------------------------------------------------------------------------- Dense Retrieval


class BaseDenseRetriever(PipelineBlock):
    """Find chunks whose *meaning* is close to the query.

    Input:  query text, optional metadata filter {field: allowed values}
    Output: RetrievalResult with Candidates (rank, chunk_id, doc_id, score), best first.
    Hyperparameters such as top_k are in self.params.
    """

    @abstractmethod
    async def retrieve(self, query: str, filters: dict[str, list[str]] | None = None) -> RetrievalResult: ...


class QdrantDenseRetriever(BaseDenseRetriever):
    """IMPLEMENTED — embed the query, then ask Qdrant for the `top_k` nearest chunk vectors (cosine)."""

    async def retrieve(self, query: str, filters: dict[str, list[str]] | None = None) -> RetrievalResult:
        db, embedder = self.services.db, self.services.embedder
        stored = db.vector_size()
        if stored is None:
            raise RuntimeError("No documents are indexed yet. Run: python scripts/ingest.py --path data/raw")
        vector = embedder.embed_query(query)
        if stored != len(vector):
            raise RuntimeError(f"Qdrant stores {stored}-dimensional vectors but the query vector has {len(vector)}. "
                               "Re-index with the current embedding method.")  # fmt: skip
        qdrant_filter = None
        if filters:  # every field must match one of its allowed values
            qdrant_filter = models.Filter(must=[models.FieldCondition(key=k, match=models.MatchAny(any=v)) for k, v in filters.items()])
        points = db.search(vector, self.params["top_k"], qdrant_filter)
        candidates = [Candidate(rank=i + 1, chunk_id=str(p.id), doc_id=p.payload["doc_id"], score=round(float(p.score), 4))
                      for i, p in enumerate(points)]  # fmt: skip
        details = {"query_vector_dimension": len(vector), "query_vector_preview": [round(v, 4) for v in vector[:8]]}
        return RetrievalResult(candidates=candidates, details=details)


# --------------------------------------------------------------------------- Lexical Retrieval


class BaseLexicalRetriever(PipelineBlock):
    """Find chunks that share *words* with the query. Same input/output as BaseDenseRetriever."""

    @abstractmethod
    async def retrieve(self, query: str, filters: dict[str, list[str]] | None = None) -> RetrievalResult: ...


class BM25Retriever(BaseLexicalRetriever):
    """PLANNED — Okapi BM25 keyword ranking."""

    async def retrieve(self, query: str, filters: dict[str, list[str]] | None = None) -> RetrievalResult:
        # TODO:
        # 1. Load all chunk texts: self.services.db.chunks.find({}, {"chunk_id": 1, "doc_id": 1, "text": 1})
        # 2. Split texts and query into lowercase words.
        # 3. Score each chunk with BM25 (parameters self.params["k1"], self.params["b"]).
        # 4. Return the top self.params["top_k"] as Candidates, best first.
        raise NotImplementedError("BM25 retrieval is not implemented yet.")


# --------------------------------------------------------------------------- Hybrid Fusion


class BaseHybridFusion(PipelineBlock):
    """Merge two candidate lists.  Input: dense and lexical Candidates.  Output: one RetrievalResult."""

    @abstractmethod
    async def fuse(self, dense: list[Candidate], lexical: list[Candidate]) -> RetrievalResult: ...


class ReciprocalRankFusion(BaseHybridFusion):
    """PLANNED — score = Σ 1 / (rrf_k + rank) over both lists."""

    async def fuse(self, dense: list[Candidate], lexical: list[Candidate]) -> RetrievalResult:
        # TODO:
        # 1. For every chunk_id, add 1 / (self.params["rrf_k"] + rank) for each list it appears in.
        # 2. Sort by that score, keep self.params["top_k"], and renumber `rank` from 1.
        raise NotImplementedError("Hybrid fusion is not implemented yet.")


# --------------------------------------------------------------------------- Metadata Enrichment (chunk lookup)


class BaseMetadataEnricher(PipelineBlock):
    """Add text and source information to candidates.  Input: Candidates.  Output: Evidence list."""

    @abstractmethod
    async def enrich(self, candidates: list[Candidate]) -> list[Evidence]: ...


class MongoChunkLookup(BaseMetadataEnricher):
    """IMPLEMENTED — load chunk text, section, page and document title from MongoDB.

    A chunk that is in Qdrant but missing in MongoDB raises an error instead of being skipped
    silently (it means the two databases are out of sync: re-index).
    """

    async def enrich(self, candidates: list[Candidate]) -> list[Evidence]:
        db = self.services.db
        chunks = db.get_chunks([c.chunk_id for c in candidates])
        documents = db.get_documents(list({c.doc_id for c in candidates}))
        missing = [c.chunk_id for c in candidates if c.chunk_id not in chunks or c.doc_id not in documents]
        if missing:
            raise RuntimeError(f"{len(missing)} chunk(s) found in Qdrant are missing in MongoDB: {missing[:3]}. Re-index the documents.")
        return [
            Evidence(rank=c.rank, chunk_id=c.chunk_id, doc_id=c.doc_id, score=c.score, text=chunks[c.chunk_id]["text"],
                     title=documents[c.doc_id]["title"], source_uri=documents[c.doc_id]["source_uri"],
                     section=chunks[c.chunk_id].get("section"), page_number=chunks[c.chunk_id].get("page_number"),
                     token_count=chunks[c.chunk_id].get("token_count", 0))
            for c in candidates
        ]  # fmt: skip
