#!/usr/bin/env python
"""Verify consistency between MongoDB and Qdrant for the active (or a given) index revision.

    conda activate RAG
    python scripts/verify_index.py
    python scripts/verify_index.py --revision <revision_id> --no-probe

Checks: collection exists; vector size/metric match the embedding contract; point and chunk
counts match; no duplicate, missing or orphan IDs; document versions exist; every chunk span
reproduces its text; active alias and MongoDB agree; self-retrieval probe (warning only).
Exit code 0 = consistent, 1 = problems found.
"""

from __future__ import annotations

import argparse
import json
import sys

import _bootstrap

from app.ingestion.pipeline import verify_revision
from app.services.embeddings import load_embedder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--revision", help="Revision ID (default: active revision)")
    parser.add_argument("--no-probe", action="store_true", help="Skip loading the embedding model for the self-retrieval probe")
    args = parser.parse_args()

    mongo, qdrant = _bootstrap.connect()
    revision = mongo.get_revision(args.revision) if args.revision else mongo.active_revision()
    if revision is None:
        sys.exit("No such revision." if args.revision else "No active index revision. Run scripts/ingest.py first.")
    embedder = None
    if not args.no_probe:
        c = revision.embedding
        embedder = load_embedder(c.model_id, c.model_revision, c.normalize, c.query_instruction, c.distance)
    result = verify_revision(mongo, qdrant, revision, embedder)

    if revision.status == "active":
        target = qdrant.active_collection()
        result["checks"]["alias_target"] = target
        if target != revision.collection_name:
            result["ok"] = False
            result["errors"].append(f"alias {qdrant.alias} points to {target}, but MongoDB marks {revision.collection_name} active")

    print(f"revision={revision.revision_id} status={revision.status} collection={revision.collection_name}")
    print(f"embedding={revision.embedding.model_id}@{(revision.embedding.model_revision or '')[:10]} dim={revision.embedding.dimension} "
          f"distance={revision.embedding.distance} normalize={revision.embedding.normalize}")  # fmt: skip
    print("checks=" + json.dumps(result["checks"]))
    for e in result["errors"]:
        print(f"ERROR: {e}")
    for w in result["warnings"]:
        print(f"warning: {w}")
    print("OK" if result["ok"] else "FAILED")
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
