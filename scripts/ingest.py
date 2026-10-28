#!/usr/bin/env python
"""Build (or reuse) a verified index revision from local documents.

    conda activate RAG
    python scripts/ingest.py --path data/raw            # real documents
    python scripts/ingest.py --path data/samples        # synthetic sample corpus
    python scripts/ingest.py --path data/raw --config my_preset.json --no-activate

--config accepts a PipelineConfig JSON ({"stages": {...}}) or an exported preset ({"config": {...}});
only offline stages (loading, parsing, chunking, metadata, embedding, indexing) are used.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap

from app.config import get_settings
from app.ingestion.pipeline import IngestionPipeline
from app.models.config import PipelineConfig
from app.rag.registry import OFFLINE_ORDER, resolve_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default="data/raw", help="Corpus directory or file (default: data/raw)")
    parser.add_argument("--config", type=Path, help="JSON configuration overriding offline-stage defaults")
    parser.add_argument("--no-activate", action="store_true", help="Build and verify without moving the active alias")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    args = parser.parse_args()

    draft = PipelineConfig()
    if args.config:
        raw = json.loads(args.config.read_text(encoding="utf-8"))
        draft = PipelineConfig(**raw.get("config", raw))
    result = resolve_config(draft, OFFLINE_ORDER)
    if not result.valid:
        sys.exit("Invalid configuration:\n" + "\n".join(f"  {e.stage_id}.{e.param or ''}: {e.message}" for e in result.errors))

    settings = get_settings()
    mongo, qdrant = _bootstrap.connect()
    path = Path(args.path).resolve()
    print(f"Ingesting {path} → Qdrant {'local ' + str(settings.qdrant_path) if qdrant.local_mode else settings.qdrant_url}")
    report = IngestionPipeline(settings, mongo, qdrant).run(path, result.resolved, activate=not args.no_activate)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        for d in report.documents:
            mark = "✓" if d.status in ("indexed", "parsed") else "✗"
            print(f"  {mark} {d.source_uri:45s} {d.chunks:4d} chunks  {d.status}" + (f"  ERROR: {d.error}" if d.error else ""))
            for w in d.warnings:
                print(f"      warning: {w}")
        for issue in report.load_issues:
            print(f"  ✗ {issue['path']}: {issue['error']}")
        print(f"\nstatus={report.status} revision={report.revision_id} collection={report.collection} activated={report.activated}")
        print(f"documents={report.doc_count} chunks={report.chunk_count} vectors_computed={report.vectors_computed} vectors_reused={report.vectors_reused}")
        v = report.verification
        if v:
            print(f"verification ok={v.get('ok')} checks={v.get('checks')}")
            for msg in v.get("errors", []) + v.get("warnings", []):
                print(f"  - {msg}")
        print(f"timings_ms={report.timings_ms}")
        if report.error:
            print(f"ERROR: {report.error}")
    sys.exit(0 if report.status in ("completed", "reused") else 1)


if __name__ == "__main__":
    main()
