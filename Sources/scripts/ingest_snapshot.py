#!/usr/bin/env python
"""Index a frozen HYU snapshot as a NEW index revision with AAES applicability tags.

BUILD → VERIFY → PUBLISH. The app's default index (synthetic fixture) is never touched.
Run from the Sources/ folder:

    conda activate RAG
    python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r1 --dry-run
    caffeinate -i python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r1
    python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r1 --publish

--dry-run needs no database and no Ollama: it loads, chunks and tags with rules only, and prints the numbers.
"""

import argparse
import asyncio
import hashlib
import json
import statistics
import sys
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

SOURCES = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SOURCES / "backend"))  # so `import app` works
sys.path.insert(0, str(SOURCES))  # so `import crawler` works

from app.config import DATA_DIR, RESULTS_DIR, get_settings  # noqa: E402
from app.database import DEFAULT_INDEX, Database  # noqa: E402
from app.ollama import OllamaClient  # noqa: E402
from app.rag.applicability import ChunkCondition  # noqa: E402
from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import LLM_CUE, ApplicabilityExtractor  # noqa: E402
from app.rag.pipeline import _with_embedder, index_documents  # noqa: E402
from app.rag.registry import create_block, validate_config  # noqa: E402
from app.rag.schemas import Services, make_doc_id  # noqa: E402
from app.rag.snapshot import HANGUL, evaluate_checks, load_snapshot, snapshot_dir, source_spans_match  # noqa: E402
from crawler.extract import EMAIL_RE  # noqa: E402

CHUNK_SIZE, CHUNK_OVERLAP, MAX_EMBED_TOKENS = 320, 48, 512
CACHE = DATA_DIR / "HYU" / "cache" / "llm_tags.jsonl"


def build_config(llm: bool) -> dict:
    return validate_config({
        "chunking": {"method": "section_tokens", "params": {"chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP}},
        "metadata_extraction": {"method": "applicability_extractor", "params": {"llm_fallback": llm}},
    })  # fmt: skip


def embedded_text(chunk: dict) -> str:
    return f"{chunk['section']}\n{chunk['text']}" if chunk["section"] else chunk["text"]


def unmasked_emails(text: str) -> int:
    return sum(1 for m in EMAIL_RE.finditer(text) if "@" in m.group(0))  # "[email]" (the mask) has no "@"


def frequency(conditions: list[dict]) -> Counter:
    freq = Counter()
    for c in conditions:
        freq[f"scope={c['scope']}"] += 1
        for attr, values in c["constraints"].items():
            for v in values:
                freq[f"{attr}={v}"] += 1
        freq["has_requirements"] += bool(c["requirements"])
        freq["has_effective_term"] += bool(c["effective_term"])
    return freq


def dry_run(args, services: Services, docs) -> int:
    config = build_config(llm=False)
    chunker = create_block("chunking", "section_tokens", config["chunking"]["params"], services)
    extractor = create_block("metadata_extraction", "applicability_extractor", config["metadata_extraction"]["params"], services)
    chunks, inputs = [], []
    for document, lookup in docs:
        for c in chunker.chunk(document):
            chunks.append({"section": c.section, "text": c.text})
            inputs.append(lookup.chunk_input(document, c))
    conditions = [c.to_dict() for c in extractor.tag_chunks(inputs)]
    tokens = [services.embedder.count_tokens(embedded_text(c)) + 2 for c in chunks]  # +2: [CLS] and [SEP]
    would_call = sum(1 for c, i in zip(conditions, inputs, strict=True) if not c["constraints"] and LLM_CUE.search(i["text"]))
    print(f"Snapshot {args.snapshot}: {len(docs)} documents, {len(chunks)} chunks (section_tokens {CHUNK_SIZE}/{CHUNK_OVERLAP})")
    print(f"Embedded tokens: max {max(tokens)}, median {statistics.median(tokens)}; over {MAX_EMBED_TOKENS}: {sum(t > MAX_EMBED_TOKENS for t in tokens)}")
    print(f"Hangul in headers: {sum(bool(c['section'] and HANGUL.search(c['section'])) for c in chunks)}; "
          f"unmasked e-mails: {sum(unmasked_emails(c['text']) for c in chunks)}")
    print(f"Rule-tagged chunks: {sum(bool(c['constraints']) for c in conditions)}; would call the LLM: {would_call}")
    print("\nAttribute frequency (rules only):")
    for key, n in sorted(frequency(conditions).items()):
        print(f"  {key:40s} {n}")
    return 0


def default_counts(db: Database) -> dict:
    info = db.index_info()
    return {k: info[k] for k in ("documents", "chunks", "vectors")}


def verify(db: Database, embedder, default_before: dict, default_after: dict, expected_documents: int,
           snapshot_id: str, applicability: dict) -> dict:  # fmt: skip
    chunks = list(db.chunks.find({}, {"_id": 0}))
    ids = {c["chunk_id"] for c in chunks}
    points, offset = [], None
    while True:
        batch, offset = db.qdrant.scroll(db.collection, limit=1024, offset=offset, with_payload=True, with_vectors=False)
        points.extend(batch)
        if offset is None:
            break
    invalid = 0
    for c in chunks:
        try:
            ChunkCondition.from_dict(c["applicability"]).validate(c["text"])
        except (KeyError, TypeError, ValueError):
            invalid += 1
    with open(snapshot_dir(snapshot_id) / "documents.jsonl", encoding="utf-8") as f:
        rows = (json.loads(line) for line in f if line.strip())
        snapshot_texts = {make_doc_id(row["source_uri"]): row["text"] for row in rows}
    span_mismatch_ids = [c["chunk_id"] for c in chunks
                         if not source_spans_match(c["text"], snapshot_texts.get(c["doc_id"], ""), c.get("source_spans", []))]  # fmt: skip
    tokens = [embedder.count_tokens(embedded_text(c)) + 2 for c in chunks]
    facts = {
        "expected_documents": expected_documents, "mongo_documents": db.documents.count_documents({}),
        "mongo_chunks": len(chunks), "qdrant_points": len(points), "dimension": db.vector_size(),
        "unique_chunk_ids": len(ids), "points_without_chunk": sum(str(p.id) not in ids for p in points),
        "max_embedded_tokens": max(tokens, default=0), "truncated_by_embedder": sum(t > MAX_EMBED_TOKENS for t in tokens),
        "invalid_applicability": invalid, "llm_errors": applicability.get("llm_errors", 0),
        "span_text_mismatches": len(span_mismatch_ids), "span_text_mismatch_chunk_ids": span_mismatch_ids[:5],
        "points_missing_app_fields": sum(not {"app_scope", "app_campus"} <= set(p.payload or {}) for p in points),
        "unmasked_emails": sum(unmasked_emails(c["text"]) for c in chunks),
        "hangul_headers": sum(bool(c["section"] and HANGUL.search(c["section"])) for c in chunks),
        "default_before": default_before, "default_after": default_after,
    }  # fmt: skip
    checks, status = evaluate_checks(facts)
    count_fields = ("tagged_by_rule", "tagged_by_llm", "llm_rejected", "llm_rejected_total", "llm_errors",
                    "llm_called", "llm_cache_hits", "unconditioned")  # fmt: skip
    return {"facts": facts, "checks": checks, "status": status,
            "applicability_counts": {key: applicability.get(key) for key in count_fields},
            "frequency": dict(sorted(frequency([c["applicability"] for c in chunks]).items()))}  # fmt: skip


def write_report(index_id: str, report: dict) -> Path:
    out = RESULTS_DIR / "index_reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{index_id}.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [f"# Index verification: {index_id}", "", f"Status: **{report['status']}**", "", "| Check | Pass |", "|---|---|",
             *(f"| {k} | {'yes' if v else 'NO'} |" for k, v in report["checks"].items()), "", "| Fact | Value |", "|---|---|",
             *(f"| {k} | {v} |" for k, v in report["facts"].items()), "", "| Applicability count | Value |", "|---|---|",
             *(f"| {k} | {v} |" for k, v in report["applicability_counts"].items()), "", "| Tag | Chunks |", "|---|---:|",
             *(f"| {k} | {v} |" for k, v in report["frequency"].items())]  # fmt: skip
    (out / f"{index_id}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out / f"{index_id}.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Index a frozen HYU snapshot (BUILD → VERIFY → PUBLISH)")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--index-id", required=True, help="new index revision, e.g. hyu_20261110_97dc1269_r1")
    parser.add_argument("--no-llm", action="store_true", help="rules only, no LLM fallback")
    parser.add_argument("--dry-run", action="store_true", help="no databases, no Ollama: load, chunk, tag (rules), print numbers")
    parser.add_argument("--publish", action="store_true", help="mark a verified index as published")
    parser.add_argument("--force", action="store_true", help="rebuild an index id that already has a manifest")
    args = parser.parse_args()
    if args.index_id == DEFAULT_INDEX:
        sys.exit("Refusing to build into the default index; choose a new --index-id.")

    settings = get_settings()
    config = build_config(llm=not args.no_llm)
    if args.dry_run:
        services = _with_embedder(config, Services(db=None, ollama=None, settings=settings))  # type: ignore[arg-type]
        docs = load_snapshot(args.snapshot, services.embedder.count_tokens, CHUNK_SIZE)
        sys.exit(dry_run(args, services, docs))

    app_db = Database.connect(settings)
    for name, state in app_db.check().items():
        if not state["ok"]:
            sys.exit(f"{name} is not reachable: {state['error']}\nStart the databases with: ./start.sh")
    db = app_db.for_index(args.index_id)
    manifest = db.get_manifest()

    if args.publish:
        if not manifest or manifest.get("status") != "verified":
            sys.exit(f"Index {args.index_id} is not verified (status: {manifest and manifest.get('status')}); nothing published.")
        db.save_manifest({**manifest, "status": "published", "published_at": datetime.now(UTC).isoformat()})
        print(f"Published {args.index_id}. Select it with index_id={args.index_id} (GET /api/indexes).")
        return
    if manifest and not args.force:
        sys.exit(f"Index {args.index_id} already exists (status {manifest.get('status')}). Use --force to rebuild it.")

    ollama = OllamaClient(settings.ollama_base_url)
    if not args.no_llm:  # fail fast: without this, a missing model only shows up as llm_errors after the whole build
        model = config["metadata_extraction"]["params"]["model"]
        installed = {m["name"]: m for m in asyncio.run(ollama.list_models())}
        if not installed.get(model, {}).get("digest"):
            sys.exit(f"Ollama model {model} is not installed (installed: {', '.join(installed)}). Run: ollama pull {model}, or use --no-llm.")
    default_before = default_counts(app_db)
    db.create_indexes()
    services = _with_embedder(config, Services(db=db, ollama=ollama, settings=settings))
    docs = load_snapshot(args.snapshot, services.embedder.count_tokens, CHUNK_SIZE)
    lookups = {d.source_uri: lookup for d, lookup in docs}

    def tag_input(document, chunk):
        return lookups[document.source_uri].chunk_input(document, chunk)

    ApplicabilityExtractor.cache_path = CACHE  # the block is created inside index_documents; this reaches it
    print(f"BUILD {args.index_id} from {args.snapshot} ({len(docs)} documents, LLM fallback {'off' if args.no_llm else 'on'}) …")
    snap_manifest = snapshot_dir(args.snapshot).parent.parent / "manifest.jsonl"
    report = index_documents([d for d, _ in docs], config, services, tag_input=tag_input,
                             source_hashes={d.source_uri: d.declared_metadata["source_sha256"] for d, _ in docs},
                             corpus={"source": f"snapshot:{args.snapshot}"})  # fmt: skip
    for message in report["errors"]:
        print(f"  ✗ {message}")
    built = {**report["manifest"], "snapshot_id": args.snapshot, "status": "built",
             "snapshot_manifest_sha256": hashlib.sha256(snap_manifest.read_bytes()).hexdigest()}  # fmt: skip
    db.save_manifest(built)
    print(f"Built: {report['documents']} documents, {report['chunks']} chunks. VERIFY …")

    result = verify(db, services.embedder, default_before, default_counts(app_db), len(docs), args.snapshot,
                    built.get("applicability") or {})  # fmt: skip
    db.save_manifest({**built, "status": result["status"], "verification": {"checks": result["checks"], "facts": result["facts"]}})
    path = write_report(args.index_id, {"index_id": args.index_id, "snapshot_id": args.snapshot,
                                        "applicability": built.get("applicability"), **result})  # fmt: skip
    for name, ok in result["checks"].items():
        print(f"  {'✓' if ok else '✗'} {name}")
    print(f"Status: {result['status']}. Report: {path}")
    if result["status"] == "verified":
        print(f"Next: python scripts/ingest_snapshot.py --snapshot {args.snapshot} --index-id {args.index_id} --publish")


if __name__ == "__main__":
    main()
