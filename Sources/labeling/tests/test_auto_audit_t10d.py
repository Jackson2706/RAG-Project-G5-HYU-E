from __future__ import annotations

import json
from collections import Counter

import mongomock

import labeling.auto_audit as auto_audit
from app.database import Database
from labeling.audit_tags import BUCKETS, _method_family
from labeling.auto_audit import (
    build_parser,
    carry_disagreement_decisions,
    compare,
    finalize,
    main,
)


def _condition(campus: str, *, any_of: bool = False) -> dict:
    return {
        "constraints": {},
        "any_of": ([{"topik_level": ["3", "4", "5", "6"]}, {"english_track": ["yes"]}] if any_of else []),
        "scope": "campus",
        "campus": [campus],
        "requirements": [],
        "effective_term": None,
        "superseded_by": None,
        "extraction_method": {"campus": "site_default", **({"any_of": "rule"} if any_of else {})},
        "evidence": {"any_of": "TOPIK level 3 or higher"} if any_of else {},
    }


def _rules_only_index(name: str = "rules-only") -> Database:
    mongo = mongomock.MongoClient()[name]
    db = Database(mongo, None, "unused", name)  # type: ignore[arg-type]
    for campus in ("seoul", "erica"):
        db.documents.insert_one(
            {
                "doc_id": f"doc-{campus}",
                "title": f"{campus.title()} guide",
                "source_uri": f"https://example.test/{campus}",
                "metadata": {"site": campus},
            }
        )
    layout = {"rule_tagged": 90, "rule_unconditioned": 40, "rule_cue_unknown": 60}
    number = 0
    for bucket, count in layout.items():
        for offset in range(count):
            campus = "seoul" if offset % 2 else "erica"
            special = bucket == "rule_tagged" and offset < 4
            text = f"Audit chunk {number}"
            if special:
                text = f"TOPIK level 3 or higher. {text}"
            db.chunks.insert_one(
                {
                    "chunk_id": f"c{number:03d}",
                    "doc_id": f"doc-{campus}",
                    "text": text,
                    "section": "Eligibility",
                    "heading_path": ["Guide", "Eligibility"],
                    "applicability": _condition(campus, any_of=special and offset < 2),
                    "tag_bucket": bucket,
                    "condition_status": "unknown" if bucket == "rule_cue_unknown" else "unconditioned",
                }
            )
            number += 1
    partition = {bucket: db.chunks.count_documents({"tag_bucket": bucket}) for bucket in BUCKETS}
    db.save_manifest({"applicability": {"partition": partition}})
    return db


def test_exclude_scales_quotas_caps_floors_and_uses_named_output(tmp_path, monkeypatch):
    db = _rules_only_index()
    excluded_ids = [f"c{number:03d}" for number in range(10, 20)]
    excluded_meta = tmp_path / "old" / "sample_meta.json"
    excluded_meta.parent.mkdir()
    excluded_meta.write_text(json.dumps({"chunk_ids": excluded_ids}), encoding="utf-8")
    monkeypatch.setattr(auto_audit, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(auto_audit, "connect_index", lambda index_id: db)

    assert main([
        "sample", "--index-id", db.index_id, "--n", "100", "--exclude", str(excluded_meta),
        "--out", "fresh",
    ]) == 0

    out = tmp_path / "results" / "tag_audit" / db.index_id / "fresh"
    metadata = json.loads((out / "sample_meta.json").read_text(encoding="utf-8"))
    assert not set(metadata["chunk_ids"]) & set(excluded_ids)
    assert metadata["excluded_files"] == [{"path": str(excluded_meta), "count": 10}]
    assert metadata["bucket_targets"]["rule_tagged"] >= 33
    assert metadata["bucket_targets"]["rule_unconditioned"] == 17
    assert metadata["bucket_targets"]["rule_cue_unknown"] >= 23
    assert metadata["bucket_targets"]["llm_tagged"] == 0
    floors = metadata["achieved_strata"]["floors"]
    assert floors["topik_text"] == {"requested": 10, "available": 4, "required": 4, "achieved": 4}
    assert floors["any_of"] == {"requested": 3, "available": 2, "required": 2, "achieved": 2}


def test_reuse_keeps_ids_recomputes_buckets_and_copies_blind_bytes(tmp_path, monkeypatch, capsys):
    db = _rules_only_index("reuse")
    chunk_ids = ["c095", "c005", "c135"]
    source = tmp_path / "old"
    source.mkdir()
    (source / "sample_meta.json").write_text(
        json.dumps({"index_id": "old", "seed": 7, "chunk_ids": chunk_ids}), encoding="utf-8"
    )
    chunks = {row["chunk_id"]: row for row in db.chunks.find({"chunk_id": {"$in": chunk_ids}}, {"_id": 0})}
    blind_bytes = b"".join(
        (json.dumps({"chunk_id": chunk_id, "text": chunks[chunk_id]["text"]}) + "\n").encode()
        for chunk_id in chunk_ids
    )
    (source / "blind_inputs.jsonl").write_bytes(blind_bytes)
    monkeypatch.setattr(auto_audit, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(auto_audit, "connect_index", lambda index_id: db)

    assert main([
        "sample", "--index-id", db.index_id, "--reuse", str(source / "sample_meta.json"),
        "--out", "reused",
    ]) == 0
    out = tmp_path / "results" / "tag_audit" / db.index_id / "reused"
    metadata = json.loads((out / "sample_meta.json").read_text(encoding="utf-8"))
    assert metadata["chunk_ids"] == chunk_ids
    assert metadata["achieved_strata"]["by_bucket"] == {
        bucket: Counter(chunks[chunk_id]["tag_bucket"] for chunk_id in chunk_ids)[bucket]
        for bucket in BUCKETS
    }
    assert (out / "blind_inputs.jsonl").read_bytes() == blind_bytes

    db.chunks.update_one({"chunk_id": chunk_ids[0]}, {"$set": {"text": "changed"}})
    assert main([
        "sample", "--index-id", db.index_id, "--reuse", str(source / "sample_meta.json"),
        "--out", "changed",
    ]) == 2
    assert "text changed" in capsys.readouterr().err


def test_carry_decisions_matches_both_value_sets_and_remaps_sides(tmp_path):
    old = [
        {"chunk_id": "c1", "attribute": "degree_level", "value_a": ["undergraduate"], "value_b": ["master"]},
        {"chunk_id": "c2", "attribute": "student_type", "value_a": ["exchange"], "value_b": ["visiting"]},
    ]
    key = {
        "seed": 1,
        "rows": [
            {"chunk_id": "c1", "attribute": "degree_level", "predicted_side": "a", "reference_side": "b"},
            {"chunk_id": "c2", "attribute": "student_type", "predicted_side": "a", "reference_side": "b"},
        ],
    }
    decisions = [
        {"chunk_id": "c1", "attribute": "degree_level", "decision": "a", "reason": "quote"},
        {"chunk_id": "c2", "attribute": "student_type", "decision": "b", "reason": "quote"},
    ]
    (tmp_path / "disagreements.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in old), encoding="utf-8"
    )
    (tmp_path / "disagreements_key.json").write_text(json.dumps(key), encoding="utf-8")
    (tmp_path / "decisions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in decisions), encoding="utf-8"
    )
    current = [
        {"chunk_id": "c1", "attribute": "degree_level", "value_a": ["master"], "value_b": ["undergraduate"]},
        {"chunk_id": "c2", "attribute": "student_type", "value_a": ["exchange"], "value_b": ["degree_seeking"]},
    ]

    new, carried_rows, carried = carry_disagreement_decisions(tmp_path, current)

    assert new == [current[1]]
    assert carried_rows == [current[0]]
    assert carried[0]["decision"] == "b"
    assert carried[0]["reason"] == "quote"


def test_finalize_merges_carried_decisions_and_reports_count(tmp_path):
    mongo = mongomock.MongoClient()["finalize"]
    db = Database(mongo, None, "unused", "finalize")  # type: ignore[arg-type]
    db.documents.insert_one(
        {"doc_id": "doc", "title": "Guide", "source_uri": "https://example.test", "metadata": {"site": "seoul"}}
    )
    db.chunks.insert_one(
        {
            "chunk_id": "c1",
            "doc_id": "doc",
            "text": "Master students",
            "section": "Eligibility",
            "applicability": _condition("seoul"),
            "tag_bucket": "rule_cue_unknown",
            "condition_status": "unknown",
        }
    )
    partition = {bucket: int(bucket == "rule_cue_unknown") for bucket in BUCKETS}
    metadata = {
        "index_id": db.index_id,
        "seed": 1,
        "chunk_ids": ["c1"],
        "chunks": {"c1": {"bucket": "rule_cue_unknown", "campus": "seoul"}},
        "bucket_partition": partition,
    }
    reference = {
        "chunk_id": "c1",
        "constraints": {"degree_level": ["master"]},
        "any_of": [],
        "scope": "campus",
        "campus": ["seoul"],
        "effective_term": None,
        "evidence": {"degree_level": "Master students"},
        "topik_scope": None,
        "audience": None,
        "out_of_vocabulary_condition": "",
        "notes": "",
    }
    reference_path = tmp_path / "reference.jsonl"
    reference_path.write_text(json.dumps(reference) + "\n", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample_meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    compare(db, db.index_id, reference_path, source)
    key = json.loads((source / "disagreements_key.json").read_text(encoding="utf-8"))["rows"][0]
    (source / "decisions.jsonl").write_text(
        json.dumps(
            {
                "chunk_id": "c1",
                "attribute": "degree_level",
                "decision": key["reference_side"],
                "reason": "The audience is stated.",
            }
        ) + "\n",
        encoding="utf-8",
    )

    current = tmp_path / "current"
    current.mkdir()
    (current / "sample_meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    scores = compare(db, db.index_id, reference_path, current, source)
    assert scores["carried_decisions"] == 1
    assert (current / "disagreements.jsonl").read_text(encoding="utf-8") == ""
    decisions = current / "decisions.jsonl"
    decisions.write_text("", encoding="utf-8")

    final = finalize(db, db.index_id, reference_path, decisions, current)

    assert final["disagreement_review"]["carried"] == 1
    assert "Carried decisions: 1." in (current / "scores_final.md").read_text(encoding="utf-8")


def test_new_bucket_is_rule_family_and_every_parser_has_out():
    assert _method_family(None, "rule_cue_unknown") == "rule"
    parser = build_parser()
    assert parser.parse_args(["sample", "--index-id", "x"]).out == "auto"
    assert parser.parse_args(["compare", "--index-id", "x", "--reference", "r"]).out == "auto"
    assert parser.parse_args([
        "finalize", "--index-id", "x", "--reference", "r", "--decisions", "d",
    ]).out == "auto"
