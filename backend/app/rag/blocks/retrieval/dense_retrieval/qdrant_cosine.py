"""IMPLEMENTED — embed the query, then ask Qdrant for the top_k nearest chunk vectors (cosine)."""

from __future__ import annotations

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
    async def retrieve(self, query: str, prefilter: RetrievalFilter | None = None) -> RetrievalResult:
        db, embedder = self.services.db, self.services.embedder
        stored = db.vector_size()
        if stored is None:
            raise RuntimeError("No documents are indexed yet. Run: python scripts/ingest.py --path data/raw")
        vector = embedder.embed_query(query)
        if stored != len(vector):
            raise RuntimeError(f"Qdrant stores {stored}-dimensional vectors but the query vector has {len(vector)}. "
                               "Re-index with the current embedding method.")  # fmt: skip
        # Prefiltering: the predicate goes INTO the search, so Qdrant ranks only eligible chunks.
        qdrant_filter = to_qdrant_filter(prefilter) if prefilter else None
        points = db.search(vector, self.params["top_k"], qdrant_filter)
        candidates = [Candidate(rank=i + 1, chunk_id=str(p.id), doc_id=p.payload["doc_id"], score=round(float(p.score), 4))
                      for i, p in enumerate(points)]  # fmt: skip
        details = {"query_vector_dimension": len(vector), "query_vector_preview": [round(v, 4) for v in vector[:8]]}
        return RetrievalResult(candidates=candidates, applied_filter=prefilter, details=details)
