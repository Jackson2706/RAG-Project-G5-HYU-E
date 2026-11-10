from __future__ import annotations

import mongomock
import pytest

import labeling  # noqa: F401  (adds backend/ to sys.path)
from app.database import Database


@pytest.fixture
def synthetic_index():
    """Eighty chunks, balanced across campuses and every T10 sampling stratum."""
    mongo = mongomock.MongoClient()["audit"]
    db = Database(mongo, None, "unused", "synthetic")  # type: ignore[arg-type]
    snapshots = []
    for campus in ("seoul", "erica"):
        doc_id = f"doc-{campus}"
        uri = f"https://example.test/{campus}"
        db.documents.insert_one({"doc_id": doc_id, "source_uri": uri, "metadata": {"site": campus}})
        spans = []
        text_parts = []
        offset = 0
        for index in range(40):
            text = f"{campus} audit chunk {index}"
            end = offset + len(text)
            kind = "table_row" if index % 5 == 0 else "paragraph"
            spans.append({"char_start": offset, "char_end": end, "kind": kind})
            text_parts.append(text)

            if index < 8 or index >= 36:
                bucket, status = "rule_tagged", "conditioned"
                constraints = {"degree_level": ["undergraduate"]}
                methods = {"degree_level": "rule"}
            elif index < 16:
                bucket, status = "llm_tagged", "conditioned"
                constraints = {"student_type": ["exchange"]}
                methods = {"student_type": "llm"}
            elif index < 24:
                bucket, status, constraints, methods = "rule_unconditioned", "unconditioned", {}, {}
            elif index < 32:
                bucket, status, constraints, methods = "llm_unconditioned", "unconditioned", {}, {}
            else:
                bucket, status, constraints, methods = "llm_rejected", "unknown", {}, {}

            applicability = {
                "constraints": constraints,
                "scope": "campus",
                "campus": [campus],
                "requirements": ["GPA 3.0"] if index % 7 == 0 else [],
                "effective_term": "2026-1" if index % 6 == 0 else None,
                "superseded_by": None,
                "extraction_method": {"campus": "site_default", "effective_term": "rule", **methods},
                "evidence": {},
            }
            db.chunks.insert_one(
                {
                    "chunk_id": f"{campus}-{index:02d}",
                    "doc_id": doc_id,
                    "text": text,
                    "section": "Audit",
                    "source_spans": [[offset, end]],
                    "applicability": applicability,
                    "tag_bucket": bucket,
                    "condition_status": status,
                }
            )
            offset = end + 1
        snapshots.append({"source_uri": uri, "text": "\n".join(text_parts), "spans": spans})
    return db, snapshots
