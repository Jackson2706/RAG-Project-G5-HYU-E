"""Integrity checks for the committed HYU snapshot."""

import hashlib
import json

import pytest

from app.config import DATA_DIR


SNAPSHOT_ID = "hyu-20261110-97dc1269"


def test_committed_snapshot_matches_manifest_and_checksums():
    snapshot_dir = DATA_DIR / "HYU" / "snapshots" / SNAPSHOT_ID
    if not snapshot_dir.is_dir():
        pytest.skip(f"committed snapshot is unavailable under configured DATA_DIR: {snapshot_dir}")

    for line in (snapshot_dir / "SNAPSHOT.sha256").read_text().splitlines():
        expected, filename = line.split("  ", 1)
        actual = hashlib.sha256((snapshot_dir / filename).read_bytes()).hexdigest()
        assert actual == expected

    rows = [json.loads(line) for line in (snapshot_dir / "documents.jsonl").read_text().splitlines()]
    assert len(rows) == 362
    assert all("doc_id" in row and "text" in row for row in rows)

    manifest = DATA_DIR / "HYU" / "manifest.jsonl"
    manifest_suffix = hashlib.sha256(manifest.read_bytes()).hexdigest()[:8]
    assert snapshot_dir.name.rsplit("-", 1)[1] == manifest_suffix
