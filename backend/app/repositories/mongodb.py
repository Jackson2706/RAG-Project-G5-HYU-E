"""MongoDB repository: documents, chunks, index revisions, traces, presets.

The methods are synchronous (PyMongo). Async callers run them with
``asyncio.to_thread`` so the FastAPI event loop is never blocked.

Document records are immutable per version: ``_id = "<doc_id>:<version_id>"``.
A rebuild therefore never overwrites the text that the active index's spans
refer to; the active index revision decides which version is current.
"""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING, UpdateOne
from pymongo.database import Database

from app.models.documents import Chunk, IndexRevision, SourceDocument
from app.models.pipeline import ExecutionTrace
from app.services.tracing import utcnow


class MongoRepository:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.documents = db["documents"]
        self.chunks = db["chunks"]
        self.facts = db["extracted_facts"]
        self.revisions = db["index_revisions"]
        self.traces = db["execution_traces"]
        self.presets = db["presets"]

    @classmethod
    def connect(cls, uri: str, db_name: str, timeout_ms: int = 3000) -> MongoRepository:
        from pymongo import MongoClient

        return cls(MongoClient(uri, serverSelectionTimeoutMS=timeout_ms, tz_aware=True)[db_name])

    def ensure_indexes(self) -> None:
        self.documents.create_index([("doc_id", ASCENDING), ("version_id", ASCENDING)], unique=True)
        self.chunks.create_index("chunk_id", unique=True)
        self.chunks.create_index([("doc_id", ASCENDING), ("version_id", ASCENDING)])
        self.chunks.create_index("index_revisions")
        self.facts.create_index("fact_id", unique=True)
        self.facts.create_index("chunk_id")
        self.revisions.create_index("revision_id", unique=True)
        self.revisions.create_index("status")
        self.traces.create_index("request_id", unique=True)
        self.traces.create_index([("session_id", ASCENDING), ("created_at", DESCENDING)])
        self.presets.create_index("preset_id", unique=True)

    def ping(self) -> bool:
        self.db.client.admin.command("ping")
        return True

    # ------------------------------------------------------------- documents

    def upsert_document(self, doc: SourceDocument) -> None:
        now = utcnow()
        data = doc.model_dump(exclude={"created_at", "updated_at"})
        self.documents.update_one(
            {"_id": f"{doc.doc_id}:{doc.version_id}"},
            {"$set": {**data, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    def set_document_status(self, doc_versions: dict[str, str], status: str) -> None:
        for doc_id, version_id in doc_versions.items():
            self.documents.update_one({"_id": f"{doc_id}:{version_id}"}, {"$set": {"ingestion_status": status, "updated_at": utcnow()}})

    def get_document(self, doc_id: str, version_id: str) -> SourceDocument | None:
        raw = self.documents.find_one({"_id": f"{doc_id}:{version_id}"}, {"_id": 0})
        return SourceDocument(**raw) if raw else None

    def get_documents(self, doc_versions: dict[str, str], with_content: bool = True) -> dict[str, SourceDocument]:
        ids = [f"{d}:{v}" for d, v in doc_versions.items()]
        projection = {"_id": 0} if with_content else {"_id": 0, "content": 0}
        out = {}
        for raw in self.documents.find({"_id": {"$in": ids}}, projection):
            raw.setdefault("content", "")
            out[raw["doc_id"]] = SourceDocument(**raw)
        return out

    # ------------------------------------------------------------- chunks

    def upsert_chunks(self, chunks: list[Chunk], revision_id: str) -> None:
        if not chunks:
            return
        ops = [
            UpdateOne({"_id": c.chunk_id}, {"$set": c.model_dump(exclude={"index_revisions"}), "$addToSet": {"index_revisions": revision_id}}, upsert=True)
            for c in chunks
        ]
        self.chunks.bulk_write(ops, ordered=False)

    def get_chunks(self, chunk_ids: list[str]) -> dict[str, Chunk]:
        return {raw["chunk_id"]: Chunk(**raw) for raw in self.chunks.find({"_id": {"$in": chunk_ids}}, {"_id": 0})}

    def chunks_for_revision(self, revision_id: str) -> list[Chunk]:
        cursor = self.chunks.find({"index_revisions": revision_id}, {"_id": 0}).sort([("doc_id", ASCENDING), ("chunk_index", ASCENDING)])
        return [Chunk(**raw) for raw in cursor]

    def remove_revision_from_chunks(self, revision_id: str) -> None:
        self.chunks.update_many({"index_revisions": revision_id}, {"$pull": {"index_revisions": revision_id}})

    # ------------------------------------------------------------- index revisions

    def save_revision(self, revision: IndexRevision) -> None:
        self.revisions.replace_one({"_id": revision.revision_id}, revision.model_dump(mode="python"), upsert=True)

    def get_revision(self, revision_id: str) -> IndexRevision | None:
        raw = self.revisions.find_one({"_id": revision_id}, {"_id": 0})
        return IndexRevision(**raw) if raw else None

    def active_revision(self) -> IndexRevision | None:
        raw = self.revisions.find_one({"status": "active"}, {"_id": 0})
        return IndexRevision(**raw) if raw else None

    def list_revisions(self) -> list[IndexRevision]:
        return [IndexRevision(**raw) for raw in self.revisions.find({}, {"_id": 0}).sort("created_at", DESCENDING)]

    def mark_active(self, revision_id: str) -> None:
        now = utcnow()
        self.revisions.update_many({"status": "active", "_id": {"$ne": revision_id}}, {"$set": {"status": "superseded"}})
        self.revisions.update_one({"_id": revision_id}, {"$set": {"status": "active", "activated_at": now}})

    # ------------------------------------------------------------- traces & presets

    def save_trace(self, trace: ExecutionTrace) -> None:
        self.traces.replace_one({"_id": trace.request_id}, trace.model_dump(mode="json"), upsert=True)

    def get_trace(self, request_id: str) -> ExecutionTrace | None:
        raw = self.traces.find_one({"_id": request_id}, {"_id": 0})
        return ExecutionTrace(**raw) if raw else None

    def list_presets(self) -> list[dict[str, Any]]:
        return list(self.presets.find({}, {"_id": 0}).sort("name", ASCENDING))

    def save_preset(self, preset: dict[str, Any]) -> None:
        self.presets.replace_one({"_id": preset["preset_id"]}, preset, upsert=True)
