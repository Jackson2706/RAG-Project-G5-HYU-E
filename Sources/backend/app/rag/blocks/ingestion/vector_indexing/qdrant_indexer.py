"""IMPLEMENTED — text in MongoDB, vectors in Qdrant (cosine), with a verified HNSW configuration."""

from __future__ import annotations

from typing import Any

from app.rag.blocks.ingestion.vector_indexing.base import BaseVectorIndexer


class QdrantMongoIndexer(BaseVectorIndexer):
    """Replaces the whole index. The Qdrant payload is {chunk_id, doc_id} plus the document's metadata
    fields (lists of lowercase values), which Metadata Prefiltering searches on.

    HNSW (approximate search) hyperparameters, used when the index is BUILT:
      hnsw_m, hnsw_ef_construct  graph size / build effort
      indexing_threshold_kb      Qdrant only builds the graph for segments larger than this (its
                                 default 20000 KB ≈ 13,000 vectors of 384 numbers); smaller indexes
                                 are always searched exactly by full scan. 1 = always build it.
    The returned status says whether the graph was really built (hnsw_built).
    """

    def index(self, documents: list[dict], chunks: list[dict], vectors: list[list[float]], dimension: int) -> dict[str, Any]:
        db, p = self.services.db, self.params
        hnsw = {"m": p["hnsw_m"], "ef_construct": p["hnsw_ef_construct"], "indexing_threshold_kb": p["indexing_threshold_kb"]}
        db.replace_index(documents, chunks, vectors, dimension, hnsw=hnsw)
        raw_kb = len(vectors) * dimension * 4 / 1024
        # The graph is built in the background; wait for it only when Qdrant is going to build one.
        return db.wait_until_indexed() if raw_kb > p["indexing_threshold_kb"] else db.vector_index_status()
