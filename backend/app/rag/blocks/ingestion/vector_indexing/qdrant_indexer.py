"""IMPLEMENTED — text in MongoDB, vectors in Qdrant (cosine)."""

from __future__ import annotations

from app.rag.blocks.ingestion.vector_indexing.base import BaseVectorIndexer


class QdrantMongoIndexer(BaseVectorIndexer):
    """Replaces the whole index. The Qdrant payload is {chunk_id, doc_id}; add metadata fields here if a
    prefilter needs them (then re-index)."""

    def index(self, documents: list[dict], chunks: list[dict], vectors: list[list[float]], dimension: int) -> None:
        self.services.db.replace_index(documents, chunks, vectors, dimension)
