"""IMPLEMENTED — embed the query, then ask Qdrant for the top_k nearest chunk vectors (cosine)."""

from __future__ import annotations

import time

from qdrant_client import models

from app.rag.blocks.retrieval.dense_retrieval.base import BaseDenseRetriever
from app.rag.schemas import Candidate, RetrievalFilter, RetrievalResult


def to_qdrant_filter(prefilter: RetrievalFilter) -> models.Filter:
    """Every field must match one of its allowed values (or be missing, if include_unknown)."""
    must = []
    for field, allowed in prefilter.conditions.items():
        match = models.FieldCondition(key=field, match=models.MatchAny(any=allowed))
        if prefilter.include_unknown:
            must.append(models.Filter(should=[match, models.IsEmptyCondition(is_empty=models.PayloadField(key=field))]))
        else:
            must.append(match)
    return models.Filter(must=must)


class QdrantDenseRetriever(BaseDenseRetriever):
    """Hyperparameters:
    top_k        how many chunks to return
    search_mode  "exact": compare the query with every vector (exact nearest neighbours, the reference);
                 "hnsw": walk Qdrant's HNSW graph (approximate, faster on large indexes). Refused when
                 the index has no HNSW graph, so an "HNSW" result is never really a full scan.
    hnsw_ef      HNSW search breadth (only for "hnsw"): larger = closer to exact, slower.
    """

    async def retrieve(self, query: str, prefilter: RetrievalFilter | None = None, embedding_text: str | None = None) -> RetrievalResult:
        db, embedder = self.services.db, self.services.embedder
        stored = db.vector_size()
        if stored is None:
            raise RuntimeError("No documents are indexed yet. Run: python scripts/ingest.py --path data/filter_ready")
        start = time.perf_counter()
        # HyDE: a hypothetical passage is embedded like a document (no query instruction).
        vector = embedder.embed_documents([embedding_text])[0] if embedding_text else embedder.embed_query(query)
        embed_ms = (time.perf_counter() - start) * 1000
        if stored != len(vector):
            raise RuntimeError(f"Qdrant stores {stored}-dimensional vectors but the query vector has {len(vector)}. "
                               "Re-index with the current embedding method.")  # fmt: skip
        mode = self.params["search_mode"]
        if mode == "hnsw":
            status = db.vector_index_status()
            if not status["hnsw_built"]:
                raise RuntimeError(f"This index has no HNSW graph ({status['indexed_vectors']}/{status['points']} vectors indexed), "
                                   "so Qdrant would do a full scan. Re-index with a lower 'Indexing threshold' or use exact search.")  # fmt: skip
            params = models.SearchParams(hnsw_ef=self.params["hnsw_ef"], exact=False)
        else:
            params = models.SearchParams(exact=True)
        # Prefiltering: the predicate goes INTO the search, so Qdrant ranks only eligible chunks.
        qdrant_filter = to_qdrant_filter(prefilter) if prefilter else None
        start = time.perf_counter()
        points = db.search(vector, self.params["top_k"], qdrant_filter, params)
        search_ms = (time.perf_counter() - start) * 1000
        candidates = [Candidate(rank=i + 1, chunk_id=str(p.id), doc_id=p.payload["doc_id"], score=round(float(p.score), 4),
                                scores={"dense": round(float(p.score), 4)}) for i, p in enumerate(points)]  # fmt: skip
        details = {"score": "cosine similarity", "search_mode": mode, "hnsw_ef": self.params["hnsw_ef"] if mode == "hnsw" else None,
                   "embedded": "hypothetical passage (HyDE)" if embedding_text else "query", "embed_ms": round(embed_ms, 2),
                   "search_ms": round(search_ms, 2), "query_vector_dimension": len(vector),
                   "query_vector_preview": [round(v, 4) for v in vector[:8]]}  # fmt: skip
        return RetrievalResult(candidates=candidates, applied_filter=prefilter, details=details)
