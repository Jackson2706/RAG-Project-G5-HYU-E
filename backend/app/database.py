"""MongoDB and Qdrant access.

MongoDB stores the readable data:   documents, chunks (with text), traces.
Qdrant stores the searchable data:  one vector per chunk.

They are linked by IDs: a Qdrant point's ID *is* the chunk's `chunk_id`, and its payload
also carries `doc_id`. So after Qdrant finds a similar vector we can look up the chunk
text in MongoDB with the same ID.
"""

from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase
from qdrant_client import QdrantClient, models

from app.config import BACKEND_DIR, Settings


class Database:
    def __init__(self, mongo: MongoDatabase, qdrant: QdrantClient, collection: str) -> None:
        self.documents = mongo["documents"]
        self.chunks = mongo["chunks"]
        self.traces = mongo["traces"]
        self.mongo = mongo
        self.qdrant = qdrant
        self.collection = collection

    @classmethod
    def connect(cls, settings: Settings) -> Database:
        mongo = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000, tz_aware=True)[settings.mongodb_db]
        if settings.qdrant_path:  # embedded Qdrant; a relative path is inside backend/
            qdrant = QdrantClient(path=str(BACKEND_DIR / settings.qdrant_path))
        else:
            qdrant = QdrantClient(url=settings.qdrant_url, timeout=10)
        return cls(mongo, qdrant, settings.qdrant_collection)

    def create_indexes(self) -> None:
        self.documents.create_index("doc_id", unique=True)
        self.chunks.create_index("chunk_id", unique=True)
        self.chunks.create_index("doc_id")
        self.traces.create_index("request_id", unique=True)

    # ----------------------------------------------------------------- health

    def check(self) -> dict[str, Any]:
        status: dict[str, Any] = {}
        try:
            self.mongo.client.admin.command("ping")
            status["mongodb"] = {"ok": True}
        except Exception as exc:
            status["mongodb"] = {"ok": False, "error": str(exc)[:200]}
        try:
            self.qdrant.get_collections()
            status["qdrant"] = {"ok": True}
        except Exception as exc:
            status["qdrant"] = {"ok": False, "error": str(exc)[:200]}
        return status

    # ----------------------------------------------------------------- writing (ingestion)

    def replace_index(self, documents: list[dict], chunks: list[dict], vectors: list[list[float]], dimension: int) -> None:
        """Replace everything with a freshly ingested corpus.

        Called only after all documents were parsed, chunked and embedded successfully,
        so a failing file never leaves the database half-updated.
        """
        if self.qdrant.collection_exists(self.collection):
            self.qdrant.delete_collection(self.collection)
        self.qdrant.create_collection(
            self.collection,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        )
        for start in range(0, len(chunks), 256):
            batch = chunks[start : start + 256]
            self.qdrant.upsert(
                self.collection,
                points=[
                    models.PointStruct(id=c["chunk_id"], vector=v, payload={"chunk_id": c["chunk_id"], "doc_id": c["doc_id"]})
                    for c, v in zip(batch, vectors[start : start + 256], strict=True)
                ],
            )
        self.documents.delete_many({})
        self.chunks.delete_many({})
        if documents:
            self.documents.insert_many([dict(d) for d in documents])
        if chunks:
            self.chunks.insert_many([dict(c) for c in chunks])

    # ----------------------------------------------------------------- reading (questions)

    def vector_size(self) -> int | None:
        """Dimension of the vectors stored in Qdrant, or None if nothing is indexed yet."""
        if not self.qdrant.collection_exists(self.collection):
            return None
        return self.qdrant.get_collection(self.collection).config.params.vectors.size  # type: ignore[union-attr]

    def search(self, vector: list[float], top_k: int, query_filter: models.Filter | None = None) -> list[models.ScoredPoint]:
        return self.qdrant.query_points(self.collection, query=vector, limit=top_k, query_filter=query_filter, with_payload=True).points

    def get_chunks(self, chunk_ids: list[str]) -> dict[str, dict]:
        return {c["chunk_id"]: c for c in self.chunks.find({"chunk_id": {"$in": chunk_ids}}, {"_id": 0})}

    def get_documents(self, doc_ids: list[str]) -> dict[str, dict]:
        return {d["doc_id"]: d for d in self.documents.find({"doc_id": {"$in": doc_ids}}, {"_id": 0})}

    def list_documents(self) -> list[dict]:
        return list(self.documents.find({}, {"_id": 0}).sort("source_uri", 1))

    def index_info(self) -> dict[str, Any]:
        """What is indexed right now and with which ingestion settings."""
        first = self.documents.find_one({}, {"_id": 0, "chunking": 1, "embedding_method": 1}) or {}
        return {
            "documents": self.documents.count_documents({}),
            "chunks": self.chunks.count_documents({}),
            "vectors": self.qdrant.count(self.collection).count if self.qdrant.collection_exists(self.collection) else 0,
            "chunking": first.get("chunking"),  # e.g. {"method": "section_tokens", "chunk_size": 256, "chunk_overlap": 32}
            "embedding_method": first.get("embedding_method"),
        }

    # ----------------------------------------------------------------- traces

    def save_trace(self, trace: dict) -> None:
        self.traces.replace_one({"request_id": trace["request_id"]}, trace, upsert=True)

    def get_trace(self, request_id: str) -> dict | None:
        return self.traces.find_one({"request_id": request_id}, {"_id": 0})
