"""Shared access to the raw rows of a frozen HYU snapshot."""

from __future__ import annotations

import json

from app.rag.snapshot import snapshot_dir

DEFAULT_SNAPSHOT_ID = "hyu-20261110-97dc1269"


def load_snapshot_rows(snapshot_id: str) -> list[dict]:
    path = snapshot_dir(snapshot_id) / "documents.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Snapshot {snapshot_id} not found at {path}")
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
