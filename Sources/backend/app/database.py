"""MongoDB and Qdrant access.

MongoDB stores the readable data:   documents, chunks (with text), traces.
Qdrant stores the searchable data:  one vector per chunk.

They are linked by IDs: a Qdrant point's ID *is* the chunk's `chunk_id`, and its payload
also carries `doc_id` (plus the document's metadata, for prefiltering). So after Qdrant finds a
similar vector we can look up the chunk text in MongoDB with the same ID.

INDEX REVISIONS. The app's own index is "default" (settings.mongodb_db + settings.qdrant_collection).
Benchmark indexes live next to it, each in its own MongoDB database `hyu_bench_<id>` and Qdrant
collection `bench_<id>`, so experiments never overwrite the app's index. Every index stores a
manifest (how it was built) in its `manifest` collection.
"""

from __future__ import annotations

import time
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase
from qdrant_client import QdrantClient, models

from app.config import BACKEND_DIR, Settings
from app.rag.schemas import metadata_values

DEFAULT_INDEX = "default"
BENCH_DB_PREFIX = "hyu_bench_"
BENCH_COLLECTION_PREFIX = "bench_"


def _applicability_payload(chunk: dict) -> dict:
    """Compact, filterable copy of a chunk's AAES tags (the app_* keys); empty for untagged indexes."""
    if not chunk.get("applicability"):
        return {}
    from app.rag.applicability import ChunkCondition

    return ChunkCondition.from_dict(chunk["applicability"]).to_payload()


class Database:
    def __init__(self, mongo: MongoDatabase, qdrant: QdrantClient, collection: str, index_id: str = DEFAULT_INDEX) -> None:
        self.documents = mongo["documents"]
        self.chunks = mongo["chunks"]
        self.traces = mongo["traces"]
        self.manifests = mongo["manifest"]
        self.mongo = mongo
        self.qdrant = qdrant
        self.collection = collection
        self.index_id = index_id

    def for_index(self, index_id: str) -> Database:
        """The same database servers, but another index revision (see the module docstring)."""
        if index_id == self.index_id:
            return self
        if index_id == DEFAULT_INDEX:
            raise ValueError("Use the app's own Database object for the default index")
        if not index_id.replace("_", "").isalnum() or index_id != index_id.lower():
            raise ValueError(f"Invalid index id '{index_id}' (use lowercase letters, digits and _)")
        return Database(self.mongo.client[BENCH_DB_PREFIX + index_id], self.qdrant, BENCH_COLLECTION_PREFIX + index_id, index_id)

    def list_index_revisions(self) -> list[dict[str, Any]]:
        """The default index plus every benchmark index that has a manifest."""
        found = [{"index_id": self.index_id, "manifest": self.get_manifest()}]
        for name in sorted(self.mongo.client.list_database_names()):
            if name.startswith(BENCH_DB_PREFIX):
                other = self.for_index(name[len(BENCH_DB_PREFIX):])
                if manifest := other.get_manifest():
                    found.append({"index_id": other.index_id, "manifest": manifest})
        return found

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

    def replace_index(self, documents: list[dict], chunks: list[dict], vectors: list[list[float]], dimension: int,
                      hnsw: dict[str, int] | None = None) -> None:
        """Replace everything with a freshly ingested corpus.

        Called only after all documents were parsed, chunked and embedded successfully,
        so a failing file never leaves the database half-updated.
        hnsw: {"m", "ef_construct", "indexing_threshold_kb"} for Qdrant's HNSW graph (None = Qdrant defaults).
        Payload: chunk_id, doc_id and each document metadata field as a list of lowercase values.
        """
        if self.qdrant.collection_exists(self.collection):
            self.qdrant.delete_collection(self.collection)
        hnsw = hnsw or {}
        self.qdrant.create_collection(
            self.collection,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            hnsw_config=models.HnswConfigDiff(m=hnsw.get("m"), ef_construct=hnsw.get("ef_construct")) if hnsw else None,
            optimizers_config=models.OptimizersConfigDiff(indexing_threshold=hnsw["indexing_threshold_kb"])
            if "indexing_threshold_kb" in hnsw else None,
        )
        metadata = {d["doc_id"]: {k: metadata_values(v) for k, v in d.get("metadata", {}).items()} for d in documents}
        for start in range(0, len(chunks), 256):
            batch = chunks[start : start + 256]
            self.qdrant.upsert(
                self.collection,
                points=[
                    models.PointStruct(id=c["chunk_id"], vector=v,
                                       payload={**metadata.get(c["doc_id"], {}), **_applicability_payload(c),
                                                "chunk_id": c["chunk_id"], "doc_id": c["doc_id"]})
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

    def search(self, vector: list[float], top_k: int, query_filter: models.Filter | None = None,
               search_params: models.SearchParams | None = None) -> list[models.ScoredPoint]:
        return self.qdrant.query_points(self.collection, query=vector, limit=top_k, query_filter=query_filter,
                                        search_params=search_params, with_payload=["doc_id"]).points

    def vector_index_status(self) -> dict[str, Any]:
        """Is the HNSW graph really built? Qdrant only builds it for segments above `indexing_threshold`;
        smaller collections are searched by full scan even when HNSW is requested."""
        info = self.qdrant.get_collection(self.collection)
        hnsw = info.config.hnsw_config
        return {"points": info.points_count, "indexed_vectors": info.indexed_vectors_count or 0, "status": str(info.status),
                "segments": info.segments_count, "hnsw_m": hnsw.m, "hnsw_ef_construct": hnsw.ef_construct,
                "indexing_threshold_kb": info.config.optimizer_config.indexing_threshold,
                "hnsw_built": bool(info.points_count) and (info.indexed_vectors_count or 0) >= (info.points_count or 0)}

    def wait_until_indexed(self, timeout_s: float = 600.0) -> dict[str, Any]:
        """Wait until Qdrant's optimizer finished building the HNSW graph (or the timeout); return the status."""
        deadline = time.monotonic() + timeout_s
        while True:
            status = self.vector_index_status()
            if (status["hnsw_built"] and status["status"].upper().endswith("GREEN")) or time.monotonic() > deadline:
                return status
            time.sleep(1.0)

    def storage_info(self) -> dict[str, Any]:
        """Measured MongoDB storage and the raw size of the stored vectors (points × dimension × 4 bytes)."""
        stats = self.mongo.command("dbStats")
        size = self.vector_size() or 0
        points = self.qdrant.count(self.collection).count if size else 0
        return {"mongodb_data_bytes": int(stats.get("dataSize", 0)), "mongodb_storage_bytes": int(stats.get("storageSize", 0)),
                "qdrant_raw_vector_bytes": points * size * 4}

    # ----------------------------------------------------------------- manifest (how this index was built)
    def save_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifests.replace_one({"_id": "manifest"}, {"_id": "manifest", **manifest}, upsert=True)

    def get_manifest(self) -> dict[str, Any] | None:
        return self.manifests.find_one({"_id": "manifest"}, {"_id": 0})

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
