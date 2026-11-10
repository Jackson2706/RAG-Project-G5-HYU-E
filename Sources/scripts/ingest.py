#!/usr/bin/env python
"""Ingest documents into MongoDB + Qdrant (replaces the current index).

Run from the project root (the hyu-compass/ folder):

    conda activate RAG
    python scripts/ingest.py --path data/raw
    python scripts/ingest.py --path data/samples --chunk-size 256 --chunk-overlap 32
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))  # so `import app` works

from app.config import get_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.ollama import OllamaClient  # noqa: E402
from app.rag.pipeline import run_ingestion  # noqa: E402
from app.rag.registry import ConfigError, default_config, validate_config  # noqa: E402
from app.rag.schemas import Services  # noqa: E402


def main() -> None:
    chunking = default_config()["chunking"]
    parser = argparse.ArgumentParser(description="Ingest documents into HYU Compass")
    parser.add_argument("--path", default="data/raw", help="folder with documents (default: data/raw)")
    parser.add_argument("--chunk-size", type=int, default=chunking["params"]["chunk_size"])
    parser.add_argument("--chunk-overlap", type=int, default=chunking["params"]["chunk_overlap"])
    args = parser.parse_args()
    try:  # the registry checks the numbers, exactly like the UI
        config = validate_config({"chunking": {"method": chunking["method"],
                                               "params": {"chunk_size": args.chunk_size, "chunk_overlap": args.chunk_overlap}}})  # fmt: skip
    except ConfigError as exc:
        sys.exit(f"Invalid settings: {exc}")

    settings = get_settings()
    db = Database.connect(settings)
    for name, state in db.check().items():
        if not state["ok"]:
            sys.exit(f"{name} is not reachable: {state['error']}\nStart the databases with: docker compose up -d")
    db.create_indexes()

    print(f"Ingesting {args.path} (chunk size {args.chunk_size}, overlap {args.chunk_overlap}) …")
    services = Services(db=db, ollama=OllamaClient(settings.ollama_base_url), settings=settings)
    report = run_ingestion(Path(args.path), config, services)
    for f in report["files"]:
        print(f"  ✓ {f['source_uri']:40s} {f['chunks']:3d} chunks  {f['title']}")
    for message in report["errors"] + report["skipped"]:
        print(f"  ✗ {message}")
    print(f"Done: {report['documents']} documents, {report['chunks']} chunks, {report['dimension']}-dimensional vectors.")


if __name__ == "__main__":
    main()
