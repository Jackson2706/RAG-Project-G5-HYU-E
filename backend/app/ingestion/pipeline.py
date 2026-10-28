"""Offline ingestion: load → parse → manifest → chunk → metadata → embed → MongoDB + Qdrant → verify → publish.

Publishing strategy: every distinct (documents × offline config × embedding
contract) combination is an *index revision* with its own Qdrant collection
``<prefix>_<revision_id>``. A new collection is built and verified while the
old one keeps serving; only then is the ``<prefix>_active`` alias moved. A
failed build never touches the active alias. Because the revision ID is a hash
of its inputs, teammates who ingest the same files with the same settings get
the same revision ID and chunk IDs.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings
from app.ingestion import metadata as md
from app.ingestion.chunking import Tokenizer, chunk_document, load_tokenizer
from app.ingestion.loaders import discover_files, stable_hash
from app.ingestion.parsers import parse_file
from app.models.config import ResolvedConfig
from app.models.documents import Chunk, IndexRevision, SourceDocument
from app.repositories.mongodb import MongoRepository
from app.repositories.qdrant import QdrantRepository
from app.services.embeddings import EmbeddingProvider, load_embedder
from app.services.tracing import utcnow

log = logging.getLogger(__name__)
_INGEST_LOCK = threading.Lock()
# Offline params that affect speed only, not the content of the index.
NON_CONTRACT_PARAMS = {"embedding": {"batch_size", "device"}}
DOC_FIELDS_IN_CHUNK = ("title", "campus", "audience", "document_type", "language", "academic_year", "publication_date")


@dataclass
class DocumentReport:
    source_uri: str
    doc_id: str | None = None
    version_id: str | None = None
    title: str | None = None
    chunks: int = 0
    status: str = "pending"
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class IngestionReport:
    corpus_path: str
    status: str = "running"  # completed | reused | failed
    revision_id: str | None = None
    collection: str | None = None
    activated: bool = False
    documents: list[DocumentReport] = field(default_factory=list)
    load_issues: list[dict[str, str]] = field(default_factory=list)
    doc_count: int = 0
    chunk_count: int = 0
    vectors_reused: int = 0
    vectors_computed: int = 0
    verification: dict[str, Any] = field(default_factory=dict)
    timings_ms: dict[str, float] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def embedder_for(config: ResolvedConfig, distance: str) -> EmbeddingProvider:
    p = config.stage("embedding").params
    return load_embedder(p["model_id"], p["model_revision"] or None, p["normalize"], p["query_instruction"], distance, p["device"])


def chunk_payload(chunk: Chunk) -> dict[str, Any]:
    m = chunk.metadata
    return {"doc_id": chunk.doc_id, "chunk_id": chunk.chunk_id, "version_id": chunk.version_id, "campus": m.get("campus"),
            "language": m.get("language"), "audience": m.get("audience", []), "document_type": m.get("document_type"),
            "topics": chunk.topics, "academic_year": m.get("academic_year")}  # fmt: skip


class IngestionPipeline:
    def __init__(self, settings: Settings, mongo: MongoRepository, qdrant: QdrantRepository,
                 embedder_factory: Callable[[ResolvedConfig, str], EmbeddingProvider] = embedder_for,
                 tokenizer_factory: Callable[[str, str | None], Tokenizer] = load_tokenizer) -> None:  # fmt: skip
        self.settings = settings
        self.mongo = mongo
        self.qdrant = qdrant
        self.embedder_factory = embedder_factory
        self.tokenizer_factory = tokenizer_factory

    def run(self, path: Path, config: ResolvedConfig, activate: bool = True, write_artifacts: bool = True) -> IngestionReport:
        if not _INGEST_LOCK.acquire(blocking=False):
            raise RuntimeError("Another ingestion is already running")
        try:
            return self._run(path, config, activate, write_artifacts)
        finally:
            _INGEST_LOCK.release()

    def _run(self, path: Path, config: ResolvedConfig, activate: bool, write_artifacts: bool) -> IngestionReport:
        report = IngestionReport(corpus_path=str(path))
        t = time.perf_counter()

        def lap(name: str) -> None:
            nonlocal t
            now = time.perf_counter()
            report.timings_ms[name] = round((now - t) * 1000, 1)
            t = now

        load, parse, chunking, meta = (config.stage(s) for s in ("document_loading", "parsing", "chunking", "metadata_extraction"))
        files, issues = discover_files(path, self.settings.data_dir, load.params)
        report.load_issues = [{"path": i.path, "error": i.error} for i in issues]
        lap("loading")

        emb = config.stage("embedding").params
        tok_id = chunking.params["tokenizer_id"]
        tokenizer = self.tokenizer_factory(tok_id, emb["model_revision"] if tok_id == emb["model_id"] else None)
        documents: list[SourceDocument] = []
        chunks: list[Chunk] = []
        for f in files:
            dr = DocumentReport(source_uri=f.source_uri, doc_id=f.doc_id)
            report.documents.append(dr)
            try:
                parsed = parse_file(f.path, f.file_type, parse.method, parse.params)
                version_id = stable_hash({"sha256": f.sha256, "parser_id": parsed.parser_id, "params": parse.params})[:16]
                fields, provenance, meta_warnings = md.extract_document_metadata(
                    parsed.declared_metadata, parsed.title, parsed.content, meta.method, meta.params, default_language="en")
                doc = SourceDocument(
                    doc_id=f.doc_id, source_uri=f.source_uri, file_path=str(f.path.relative_to(self.settings.data_dir.parent))
                    if f.path.is_relative_to(self.settings.data_dir.parent) else f.path.name,
                    media_type=f.media_type, size_bytes=f.size_bytes, source_sha256=f.sha256, parser_id=parsed.parser_id,
                    version_id=version_id, page_count=parsed.page_count, content=parsed.content,
                    parse_warnings=parsed.warnings + meta_warnings, metadata_provenance=provenance, **fields,
                )  # fmt: skip
                doc_chunks = chunk_document(parsed, doc.doc_id, version_id, chunking.method, chunking.params, tokenizer)
                if not doc_chunks:
                    raise ValueError("document produced no chunks")
                for c in doc_chunks:
                    c.metadata = {k: getattr(doc, k) for k in DOC_FIELDS_IN_CHUNK}
                    c.keywords = md.top_keywords(c.text, meta.params.get("keywords_per_chunk", 8))
                    chunk_topics = md.detect_topics(c.text) if meta.method == "rule_based" and meta.params.get("detect_topics") else []
                    c.topics = sorted(set(doc.topics) | set(chunk_topics))
                documents.append(doc)
                chunks += doc_chunks
                dr.version_id, dr.title, dr.chunks, dr.status, dr.warnings = version_id, doc.title, len(doc_chunks), "parsed", doc.parse_warnings
            except Exception as exc:  # recorded per file; the file is excluded from this revision
                log.warning("ingestion failed for %s: %s", f.source_uri, exc)
                dr.status, dr.error = "failed", f"{exc.__class__.__name__}: {exc}"
        lap("parse_chunk_metadata")
        if not documents:
            report.status, report.error = "failed", "No documents could be ingested" + ("" if files else f" — no supported files under {path}")
            return report

        vi = config.stage("vector_indexing").params
        embedder = self.embedder_factory(config, vi["distance"])
        contract = embedder.contract
        contract_cfg = {
            sid: {"method": config.stage(sid).method,
                  "params": {k: v for k, v in config.stage(sid).params.items() if k not in NON_CONTRACT_PARAMS.get(sid, set())}}
            for sid in ("parsing", "chunking", "metadata_extraction", "embedding", "vector_indexing")
        }  # fmt: skip
        doc_versions = {d.doc_id: d.version_id for d in sorted(documents, key=lambda d: d.doc_id)}
        revision_id = stable_hash({"contract": contract.model_dump(), "config": contract_cfg, "docs": doc_versions,
                                   "chunks": sorted(c.chunk_id for c in chunks)})[:12]  # fmt: skip
        collection = f"{self.settings.qdrant_collection_prefix}_{revision_id}"
        report.revision_id, report.collection = revision_id, collection
        report.doc_count, report.chunk_count = len(documents), len(chunks)

        existing = self.mongo.get_revision(revision_id)
        if existing and existing.status in ("verified", "active", "superseded") and self.qdrant.collection_exists(collection):
            verification = verify_revision(self.mongo, self.qdrant, existing, embedder)
            if verification["ok"]:
                report.status, report.verification = "reused", verification
                if activate:
                    self._publish(existing, documents)
                    report.activated = True
                self._finish_docs(report, "indexed" if activate else "parsed")
                lap("verify")
                return report

        revision = IndexRevision(revision_id=revision_id, collection_name=collection, status="building", embedding=contract,
                                 offline_config={sid: config.stage(sid).model_dump() for sid in config.stages},
                                 doc_versions=doc_versions, doc_count=len(documents), chunk_count=len(chunks), created_at=utcnow())  # fmt: skip
        try:
            self.qdrant.delete_collection(collection)  # leftover of an earlier failed build
            self.qdrant.create_collection(collection, contract.dimension, vi["distance"], vi["hnsw_m"], vi["hnsw_ef_construct"])
            vectors = self._reuse_vectors(chunks, contract.contract_hash())
            missing = [c for c in chunks if c.chunk_id not in vectors]
            if missing:
                computed = embedder.embed_documents([c.embedding_text for c in missing], batch_size=emb["batch_size"])
                vectors.update({c.chunk_id: v for c, v in zip(missing, computed, strict=True)})
            revision.vectors_reused, revision.vectors_computed = len(chunks) - len(missing), len(missing)
            report.vectors_reused, report.vectors_computed = revision.vectors_reused, revision.vectors_computed
            lap("embedding")
            self.qdrant.upsert(collection, [c.chunk_id for c in chunks], [vectors[c.chunk_id] for c in chunks], [chunk_payload(c) for c in chunks])
            for d in documents:
                self.mongo.upsert_document(d)
            self.mongo.upsert_chunks(chunks, revision_id)
            self.mongo.save_revision(revision)
            lap("persist")
            revision.verification = verify_revision(self.mongo, self.qdrant, revision, embedder)
            report.verification = revision.verification
            lap("verify")
            if not revision.verification["ok"]:
                raise RuntimeError("index verification failed: " + "; ".join(revision.verification["errors"]))
            revision.status = "verified"
            self.mongo.save_revision(revision)
            if activate:
                self._publish(revision, documents)
                report.activated = True
            report.status = "completed"
            self._finish_docs(report, "indexed" if activate else "parsed")
        except Exception as exc:
            log.exception("index build %s failed", revision_id)
            revision.status = "failed"
            revision.verification.setdefault("errors", []).append(str(exc))
            self.mongo.save_revision(revision)
            self.mongo.remove_revision_from_chunks(revision_id)
            self.qdrant.delete_collection(collection)
            report.status, report.error = "failed", f"{exc.__class__.__name__}: {exc}"
            return report
        if write_artifacts:
            self._write_artifacts(revision, documents, chunks)
        return report

    def _reuse_vectors(self, chunks: list[Chunk], contract_hash: str) -> dict[str, list[float]]:
        """Copy vectors of unchanged chunks from the active revision if it uses the same embedding contract."""
        active = self.mongo.active_revision()
        if not active or active.embedding.contract_hash() != contract_hash:
            return {}
        return self.qdrant.retrieve_vectors(active.collection_name, [c.chunk_id for c in chunks])

    def _publish(self, revision: IndexRevision, documents: list[SourceDocument]) -> None:
        self.qdrant.point_alias_to(revision.collection_name)
        self.mongo.mark_active(revision.revision_id)
        self.mongo.set_document_status(revision.doc_versions, "indexed")

    @staticmethod
    def _finish_docs(report: IngestionReport, status: str) -> None:
        for d in report.documents:
            if d.status == "parsed":
                d.status = status

    def _write_artifacts(self, revision: IndexRevision, documents: list[SourceDocument], chunks: list[Chunk]) -> None:
        """Deterministic manifest (commit-able, comparable across teammates) and processed chunk dump."""
        manifests = self.settings.data_dir / "manifests"
        processed = self.settings.data_dir / "processed" / revision.revision_id
        manifests.mkdir(parents=True, exist_ok=True)
        processed.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}
        for c in chunks:
            counts[c.doc_id] = counts.get(c.doc_id, 0) + 1
        manifest = {
            "revision_id": revision.revision_id,
            "collection": revision.collection_name,
            "embedding_contract": revision.embedding.model_dump(),
            "offline_config": revision.offline_config,
            "documents": [{"doc_id": d.doc_id, "source_uri": d.source_uri, "media_type": d.media_type, "source_sha256": d.source_sha256,
                           "parser_id": d.parser_id, "version_id": d.version_id, "title": d.title, "chunks": counts.get(d.doc_id, 0)}
                          for d in sorted(documents, key=lambda d: d.source_uri)],
            "chunk_count": len(chunks),
        }  # fmt: skip
        (manifests / f"{revision.revision_id}.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
        with (processed / "chunks.jsonl").open("w", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(json.dumps(c.model_dump(exclude={"index_revisions"}), ensure_ascii=False) + "\n")


def verify_revision(mongo: MongoRepository, qdrant: QdrantRepository, revision: IndexRevision,
                    embedder: EmbeddingProvider | None = None, probes: int = 5) -> dict[str, Any]:  # fmt: skip
    """Consistency checks between the revision record, MongoDB and Qdrant. Used before publishing and by scripts/verify_index.py."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}
    name = revision.collection_name
    if not qdrant.collection_exists(name):
        return {"ok": False, "errors": [f"Qdrant collection {name} does not exist"], "warnings": [], "checks": {}}
    size, distance = qdrant.vector_params(name)
    checks["vector_size"], checks["distance"] = size, distance
    if size != revision.embedding.dimension:
        errors.append(f"collection vector size {size} != contract dimension {revision.embedding.dimension}")
    if distance != revision.embedding.distance:
        errors.append(f"collection distance {distance} != contract distance {revision.embedding.distance}")
    if embedder is not None and embedder.contract.contract_hash() != revision.embedding.contract_hash():
        errors.append("query embedder contract differs from the revision's embedding contract")
    point_ids = qdrant.all_point_ids(name)
    chunks = mongo.chunks_for_revision(revision.revision_id)
    chunk_ids = {c.chunk_id for c in chunks}
    checks.update(points=len(point_ids), unique_points=len(set(point_ids)), mongo_chunks=len(chunks), expected_chunks=revision.chunk_count)
    if len(point_ids) != len(set(point_ids)):
        errors.append("duplicate point IDs in Qdrant")
    if len(point_ids) != revision.chunk_count or len(chunks) != revision.chunk_count:
        errors.append(f"count mismatch: qdrant={len(point_ids)} mongo={len(chunks)} expected={revision.chunk_count}")
    missing_vectors = chunk_ids - set(point_ids)
    orphan_points = set(point_ids) - chunk_ids
    if missing_vectors:
        errors.append(f"{len(missing_vectors)} chunks have no vector")
    if orphan_points:
        errors.append(f"{len(orphan_points)} points have no MongoDB chunk")
    docs = mongo.get_documents(revision.doc_versions)
    missing_docs = set(revision.doc_versions) - set(docs)
    if missing_docs:
        errors.append(f"{len(missing_docs)} document versions missing in MongoDB")
    stale = [c.chunk_id for c in chunks if revision.doc_versions.get(c.doc_id) != c.version_id]
    if stale:
        errors.append(f"{len(stale)} chunks reference a document version outside this revision")
    span_failures = [c.chunk_id for c in chunks if c.doc_id in docs and docs[c.doc_id].content[c.source_span.start : c.source_span.end] != c.text]
    checks["span_failures"] = len(span_failures)
    if span_failures:
        errors.append(f"{len(span_failures)} chunk spans do not reproduce the chunk text")
    if embedder is not None and chunks and not errors:
        # Self-retrieval probe: a chunk's own text should retrieve that chunk first. Overlapping or
        # near-duplicate chunks can legitimately fail this, so it only warns.
        step = max(1, len(chunks) // probes)
        sample = chunks[::step][:probes]
        hits = 0
        for c in sample:
            vec = embedder.embed_documents([c.embedding_text])[0]
            top = qdrant.search(vec, 1, None, exact=True, hnsw_ef=None, score_threshold=None, collection=name)
            hits += bool(top) and str(top[0].id) == c.chunk_id
        checks["self_retrieval"] = f"{hits}/{len(sample)}"
        if hits < len(sample):
            warnings.append(f"self-retrieval probe matched {hits}/{len(sample)} chunks")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "checks": checks}
