from __future__ import annotations

import json
import math
from collections import Counter

import mongomock
import pytest

from app.database import Database
from labeling.auto_audit import (
    ReferenceValidationError,
    blind_row,
    compare,
    disagreement_rows,
    read_decisions,
    sample_metadata,
    sample_records,
    score_comparison,
    validate_reference,
    write_sample,
)
from labeling.audit_tags import BUCKETS, AuditError, wilson_interval


def _condition(
    campus: str,
    constraints: dict[str, list[str]] | None = None,
    *,
    any_of: list[dict[str, list[str]]] | None = None,
    methods: dict[str, str] | None = None,
    evidence: dict[str, str] | None = None,
) -> dict:
    return {
        "constraints": constraints or {},
        "any_of": any_of or [],
        "scope": "campus",
        "campus": [campus],
        "requirements": [],
        "effective_term": None,
        "superseded_by": None,
        "extraction_method": {"campus": "site_default", **(methods or {})},
        "evidence": evidence or {},
    }


def _insert_chunk(
    db: Database,
    campus: str,
    number: int,
    bucket: str,
    text: str,
    condition: dict | None = None,
) -> None:
    doc_id = f"doc-{campus}"
    db.chunks.insert_one(
        {
            "chunk_id": f"{campus}-{number:03d}",
            "doc_id": doc_id,
            "text": text,
            "section": "Eligibility",
            "heading_path": ["Guide", "Eligibility"],
            "applicability": condition or _condition(campus),
            "tag_bucket": bucket,
            "condition_status": "conditioned" if bucket.endswith("_tagged") else "unconditioned",
        }
    )


def _sampling_index() -> Database:
    mongo = mongomock.MongoClient()["auto-audit"]
    db = Database(mongo, None, "unused", "synthetic_auto")  # type: ignore[arg-type]
    for campus in ("seoul", "erica"):
        db.documents.insert_one(
            {
                "doc_id": f"doc-{campus}",
                "title": f"{campus.title()} guide",
                "source_uri": f"https://example.test/{campus}",
                "metadata": {"site": campus, "post_date": "2026-11-01"},
            }
        )
    layout = {
        "rule_tagged": 70,
        "rule_unconditioned": 30,
        "llm_tagged": 15,
        "llm_unconditioned": 45,
        "llm_rejected": 12,
        "llm_errors": 0,
    }
    number = 0
    for bucket, count in layout.items():
        for offset in range(count):
            campus = "erica" if offset % 2 == 0 else "seoul"
            text = f"General audit text {number}"
            constraints: dict[str, list[str]] = {}
            any_of: list[dict[str, list[str]]] = []
            methods: dict[str, str] = {}
            evidence: dict[str, str] = {}
            if bucket.endswith("_tagged"):
                constraints = {"degree_level": ["undergraduate"]}
                methods = {"degree_level": "llm" if bucket.startswith("llm") else "rule"}
                evidence = {"degree_level": "Undergraduate"}
                text = f"Undergraduate students. {text}"
            if bucket == "llm_tagged" or (bucket == "rule_tagged" and offset < 8):
                text = f"TOPIK level 3 or higher. {text}"
            if bucket == "rule_tagged" and offset < 8:
                constraints = {}
                any_of = [{"topik_level": ["3", "4", "5", "6"]}, {"english_track": ["yes"]}]
                methods = {"any_of": "rule"}
                evidence = {"any_of": "TOPIK level 3 or higher"}
            condition = _condition(
                campus,
                constraints,
                any_of=any_of,
                methods=methods,
                evidence=evidence,
            )
            _insert_chunk(db, campus, number, bucket, text, condition)
            number += 1
    db.save_manifest({"applicability": {"partition": layout}})
    return db


def _records(db: Database) -> list[dict]:
    documents = {row["doc_id"]: row for row in db.documents.find({}, {"_id": 0})}
    records = []
    for chunk in db.chunks.find({}, {"_id": 0}):
        document = documents[chunk["doc_id"]]
        records.append(
            {
                **chunk,
                "_campus": document["metadata"]["site"],
                "_title": document["title"],
                "_post_date": document["metadata"]["post_date"],
                "_heading_path": chunk["heading_path"],
            }
        )
    return records


def test_sampling_meets_quotas_floors_is_seeded_and_blind(tmp_path):
    db = _sampling_index()
    records = _records(db)
    first, targets = sample_records(records, seed=20261111)
    second, second_targets = sample_records(list(reversed(records)), seed=20261111)

    assert [row["chunk_id"] for row in first] == [row["chunk_id"] for row in second]
    assert targets == second_targets
    counts = Counter(row["tag_bucket"] for row in first)
    assert len(first) == 150
    assert counts["rule_tagged"] >= 50
    assert counts["rule_unconditioned"] == 25
    assert counts["llm_tagged"] == 15  # every available chunk because the bucket has fewer than 20
    assert counts["llm_unconditioned"] >= 35
    assert counts["llm_rejected"] == 12
    assert counts["llm_errors"] == 0
    assert sum("TOPIK" in row["text"] for row in first) >= 15
    assert sum(bool(row["applicability"]["any_of"]) for row in first) >= 4
    for bucket, count in counts.items():
        available_erica = sum(row["tag_bucket"] == bucket and row["_campus"] == "erica" for row in records)
        if available_erica >= math.ceil(count * 0.3):
            assert sum(row["tag_bucket"] == bucket and row["_campus"] == "erica" for row in first) >= math.ceil(count * 0.3)

    partition = db.get_manifest()["applicability"]["partition"]
    metadata = sample_metadata(db.index_id, 20261111, first, targets, partition)
    write_sample(first, metadata, tmp_path)
    blind = [json.loads(line) for line in (tmp_path / "blind_inputs.jsonl").read_text().splitlines()]
    forbidden = {"applicability", "tag_bucket", "condition_status", "extraction_method"}
    assert all(not forbidden & set(row) for row in blind)
    assert set(blind[0]) == {"chunk_id", "site", "title", "heading_path", "post_date", "text"}
    with pytest.raises(AuditError, match="Refusing to overwrite"):
        write_sample(first, metadata, tmp_path)


def _reference(chunk_id: str, campus: str, text: str, **changes) -> dict:
    row = {
        "chunk_id": chunk_id,
        "constraints": {},
        "any_of": [],
        "scope": "campus",
        "campus": [campus],
        "effective_term": None,
        "evidence": {},
        "topik_scope": None,
        "audience": None,
        "out_of_vocabulary_condition": "",
        "notes": "",
    }
    row.update(changes)
    return row


def _comparison_case():
    rows = [
        {
            "chunk_id": "c1", "text": "Undergraduate students", "tag_bucket": "rule_tagged", "_campus": "seoul",
            "_heading_path": ["A"], "applicability": _condition("seoul", {"degree_level": ["undergraduate"]}, methods={"degree_level": "rule"}),
        },
        {
            "chunk_id": "c2", "text": "Doctoral students", "tag_bucket": "rule_tagged", "_campus": "seoul",
            "_heading_path": ["B"], "applicability": _condition("seoul", {"degree_level": ["master"]}, methods={"degree_level": "rule"}),
        },
        {
            "chunk_id": "c3", "text": "TOPIK level 3 or higher or English track", "tag_bucket": "llm_tagged", "_campus": "erica",
            "_heading_path": ["C"], "applicability": _condition(
                "erica", any_of=[{"topik_level": ["3", "4", "5", "6"]}, {"english_track": ["yes"]}],
                methods={"any_of": "llm"}, evidence={"any_of": "TOPIK level 3 or higher or English track"},
            ),
        },
        {
            "chunk_id": "c4", "text": "Master students", "tag_bucket": "llm_unconditioned", "_campus": "erica",
            "_heading_path": ["D"], "applicability": _condition("erica"),
        },
    ]
    references = [
        _reference("c1", "seoul", rows[0]["text"], constraints={"degree_level": ["undergraduate"]}, evidence={"degree_level": "Undergraduate students"}),
        _reference("c2", "seoul", rows[1]["text"], constraints={"degree_level": ["doctoral"]}, evidence={"degree_level": "Doctoral students"}),
        _reference(
            "c3", "erica", rows[2]["text"],
            any_of=[{"topik_level": ["3", "4", "5", "6"]}, {"english_track": ["yes"]}],
            evidence={"any_of": "TOPIK level 3 or higher or English track"}, topik_scope="whole_chunk",
        ),
        _reference("c4", "erica", rows[3]["text"], constraints={"degree_level": ["master"]}, evidence={"degree_level": "Master students"}),
    ]
    partition = {bucket: 0 for bucket in BUCKETS}
    partition.update(rule_tagged=2, llm_tagged=1, llm_unconditioned=1)
    metadata = {
        "index_id": "four",
        "seed": 20261111,
        "chunk_ids": [row["chunk_id"] for row in rows],
        "chunks": {row["chunk_id"]: {"bucket": row["tag_bucket"], "campus": row["_campus"]} for row in rows},
        "bucket_partition": partition,
    }
    return rows, references, metadata


def test_compare_matches_hand_computed_counts_any_of_and_method_splits():
    """Degree has TP=1, FP=1, FN=2, so P=1/2 and R=1/3.

    Rule gets TP=1, FP=1, FN=1. LLM gets FN=1 from its unconditioned
    chunk. The any_of chunk gives topik TP=4 and English-track TP=1.
    """
    rows, references, metadata = _comparison_case()
    scores = score_comparison(rows, references, metadata)

    degree = scores["per_attribute"]["degree_level"]
    assert (degree["tp"], degree["fp"], degree["fn"]) == (1, 1, 2)
    assert degree["precision"] == pytest.approx(1 / 2)
    assert degree["recall"] == pytest.approx(1 / 3)
    assert degree["precision_ci"] == pytest.approx(wilson_interval(1, 2))
    assert scores["by_method"]["rule"]["degree_level"]["tp"] == 1
    assert scores["by_method"]["rule"]["degree_level"]["fp"] == 1
    assert scores["by_method"]["rule"]["degree_level"]["fn"] == 1
    assert scores["by_method"]["llm"]["degree_level"]["fn"] == 1
    assert scores["per_attribute"]["topik_level"]["tp"] == 4
    assert scores["per_attribute"]["english_track"]["tp"] == 1
    assert scores["any_of_exact_match"]["chunks_with_any_of"] == {"matches": 1, "n": 1, "rate": 1.0}


def test_disagreement_sides_are_seeded_and_key_maps_them_back():
    rows, references, metadata = _comparison_case()
    first, key = disagreement_rows(rows, references, metadata["seed"])
    second, second_key = disagreement_rows(rows, references, metadata["seed"])
    assert first == second
    assert key == second_key

    predicted = {row["chunk_id"]: row["applicability"] for row in rows}
    key_rows = {(row["chunk_id"], row["attribute"]): row for row in key["rows"]}
    for disagreement in first:
        pair = (disagreement["chunk_id"], disagreement["attribute"])
        side = key_rows[pair]["predicted_side"]
        expected = sorted(
            value
            for value in predicted[pair[0]].get("constraints", {}).get(pair[1], [])
        )
        assert disagreement[f"value_{side}"] == expected
    assert any(row["predicted_side"] == "b" for row in key["rows"])


def test_compare_writes_raw_scores_and_keeps_the_side_key_separate(tmp_path):
    rows, references, metadata = _comparison_case()
    mongo = mongomock.MongoClient()["compare"]
    db = Database(mongo, None, "unused", "four")  # type: ignore[arg-type]
    for campus in ("seoul", "erica"):
        db.documents.insert_one(
            {
                "doc_id": f"doc-{campus}",
                "title": "Guide",
                "source_uri": f"https://example.test/{campus}",
                "metadata": {"site": campus},
            }
        )
    for row in rows:
        db.chunks.insert_one(
            {
                "chunk_id": row["chunk_id"],
                "doc_id": f"doc-{row['_campus']}",
                "text": row["text"],
                "section": row["_heading_path"][-1],
                "applicability": row["applicability"],
                "tag_bucket": row["tag_bucket"],
                "condition_status": "conditioned",
            }
        )
    (tmp_path / "sample_meta.json").write_text(json.dumps(metadata))
    reference_path = tmp_path / "reference.jsonl"
    reference_path.write_text("".join(json.dumps(row) + "\n" for row in references))

    scores = compare(db, db.index_id, reference_path, tmp_path)

    assert scores["per_attribute"]["degree_level"]["fn"] == 2
    disagreement = json.loads((tmp_path / "disagreements.jsonl").read_text().splitlines()[0])
    assert "predicted_side" not in disagreement and "reference_side" not in disagreement
    assert "predicted_side" in (tmp_path / "disagreements_key.json").read_text()
    assert (tmp_path / "scores_raw.md").read_text().startswith("**Limitation (state it in every report):**")


def test_finalize_decisions_apply_a_b_both_wrong_and_ambiguous(tmp_path):
    disagreements = [
        {"chunk_id": f"c{i}", "attribute": "degree_level", "value_a": ["undergraduate"], "value_b": ["master"]}
        for i in range(1, 5)
    ]
    key = {
        "rows": [
            {"chunk_id": "c1", "attribute": "degree_level", "predicted_side": "a", "reference_side": "b"},
            {"chunk_id": "c2", "attribute": "degree_level", "predicted_side": "b", "reference_side": "a"},
            {"chunk_id": "c3", "attribute": "degree_level", "predicted_side": "a", "reference_side": "b"},
            {"chunk_id": "c4", "attribute": "degree_level", "predicted_side": "b", "reference_side": "a"},
        ]
    }
    decisions = [
        {"chunk_id": "c1", "attribute": "degree_level", "decision": "a", "reason": "quote"},
        {"chunk_id": "c2", "attribute": "degree_level", "decision": "b", "reason": "quote"},
        {"chunk_id": "c3", "attribute": "degree_level", "decision": "both_wrong", "correct_values": ["doctoral"], "reason": "quote"},
        {"chunk_id": "c4", "attribute": "degree_level", "decision": "ambiguous", "reason": "quote"},
    ]
    path = tmp_path / "decisions.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in decisions))

    overrides, excluded, summary, ambiguous = read_decisions(path, disagreements, key)
    assert overrides[("c1", "degree_level")] == {"undergraduate"}
    assert overrides[("c2", "degree_level")] == {"master"}
    assert overrides[("c3", "degree_level")] == {"doctoral"}
    assert excluded == {("c4", "degree_level")}
    assert summary == {"predicted": 2, "reference": 0, "both_wrong": 1, "ambiguous": 1}
    assert ambiguous == [{"chunk_id": "c4", "attribute": "degree_level", "reason": "quote"}]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"constraints": {"degree_level": ["postdoc"]}, "evidence": {"degree_level": "students"}}, "outside vocabulary v1"),
        ({"constraints": {"degree_level": ["undergraduate"]}, "evidence": {"degree_level": "invented quote"}}, "quote is not in"),
    ],
)
def test_reference_validator_rejects_unknown_value_and_invented_quote(tmp_path, changes, message):
    record = {
        "chunk_id": "c1",
        "text": "Undergraduate students",
        "_campus": "seoul",
        "_heading_path": [],
        "tag_bucket": "rule_tagged",
        "applicability": _condition("seoul"),
    }
    reference = _reference("c1", "seoul", record["text"], **changes)
    path = tmp_path / "reference.jsonl"
    path.write_text(json.dumps(reference) + "\n")

    with pytest.raises(ReferenceValidationError, match=message):
        validate_reference(path, [record], ["c1"])


def test_blind_row_never_exposes_prediction_fields():
    db = _sampling_index()
    row = blind_row(_records(db)[0])
    assert not {"applicability", "tag_bucket", "condition_status", "extraction_method"} & set(row)
