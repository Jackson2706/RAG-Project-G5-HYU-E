"""Benchmark index revisions: build (or reuse) one index per dataset and offline configuration.

Every index is built with the app's own index_documents() into its own MongoDB database and Qdrant
collection (Database.for_index), so the app's index is never touched. An index is reused only when
its manifest records the same offline configuration and the same corpus checksum.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import replace

from app.database import Database
from app.rag.pipeline import index_documents, run_ingestion
from app.rag.schemas import ParsedDocument, Services

OFFLINE_STAGES = ("parsing", "chunking", "metadata_extraction", "embedding", "vector_indexing")


def index_id(dataset: str, key: str, smoke: bool = False) -> str:
    return f"{dataset}_{key}" + ("_smoke" if smoke else "")


def corpus_checksum(documents: list[ParsedDocument]) -> str:
    digest = hashlib.sha256()
    for d in sorted(documents, key=lambda d: d.source_uri):
        digest.update(d.source_uri.encode())
        digest.update(d.full_text().encode())
    return digest.hexdigest()


def offline_part(config: dict) -> dict:
    return {s: config[s] for s in OFFLINE_STAGES}


def is_current(db: Database, config: dict, checksum: str) -> bool:
    manifest = db.get_manifest()
    return bool(manifest) and manifest.get("config") == offline_part(config) and manifest.get("corpus", {}).get("checksum") == checksum


def ensure_index(services: Services, idx: str, config: dict, documents: list[ParsedDocument], corpus: dict, force: bool = False) -> tuple[Database, str]:
    """The index revision `idx` built from `documents` with `config`; ("reused" | "built")."""
    db = services.db.for_index(idx)
    checksum = corpus_checksum(documents)
    if not force and is_current(db, config, checksum):
        return db, "reused"
    print(f"  building index {idx}: {len(documents)} documents, chunking={config['chunking']['method']} "
          f"{config['chunking']['params']}, embedding={config['embedding']['method']} …", flush=True)  # fmt: skip
    start = time.perf_counter()
    report = index_documents(documents, config, replace(services, db=db, embedder=None), corpus={**corpus, "checksum": checksum})
    print(f"  built {idx}: {report['chunks']} chunks in {time.perf_counter() - start:.0f} s "
          f"(HNSW built: {report['manifest']['vector_index'].get('hnsw_built')})", flush=True)  # fmt: skip
    return db, "built"


def ensure_folder_index(services: Services, idx: str, config: dict, folder, force: bool = False) -> tuple[Database, str]:
    """An index of a folder of files (the HYU sample documents), built with run_ingestion() like the app does."""
    db = services.db.for_index(idx)
    files = sorted(p for p in folder.iterdir() if p.is_file())
    checksum = hashlib.sha256(b"".join(p.name.encode() + p.read_bytes() for p in files)).hexdigest()
    if not force and (m := db.get_manifest()) and m.get("config") == offline_part(config) and m.get("folder_checksum") == checksum:
        return db, "reused"
    run_ingestion(folder, config, replace(services, db=db, embedder=None))
    db.manifests.update_one({"_id": "manifest"}, {"$set": {"folder_checksum": checksum}})
    return db, "built"
