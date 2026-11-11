from __future__ import annotations

import json
import math
from collections import Counter

import mongomock
import pytest

import labeling.auto_audit as auto_audit
from app.database import Database
from labeling.audit_tags import BUCKETS, wilson_interval
from labeling.auto_audit import cue_name, main, score_comparison, scores_markdown


def _condition(
    campus: str,
    degree: str | None = None,
    *,
    applicant: bool = False,
) -> dict:
    constraints = {}
    methods = {"campus": "site_default"}
    if degree:
        constraints["degree_level"] = [degree]
        methods["degree_level"] = "rule"
    if applicant:
        constraints["academic_status"] = ["applicant"]
        methods["academic_status"] = "rule"
    return {
        "constraints": constraints,
        "any_of": [],
        "scope": "campus",
        "campus": [campus],
        "effective_term": None,
        "extraction_method": methods,
        "evidence": {},
    }


def _reference(chunk_id: str, degree: str | None) -> dict:
    return {
        "chunk_id": chunk_id,
        "constraints": {"degree_level": [degree]} if degree else {},
        "any_of": [],
        "scope": "campus",
        "campus": ["seoul"],
        "effective_term": None,
    }


def _design_case() -> tuple[list[dict], list[dict], dict]:
    rows = [
        ("c1", "rule_tagged", "rule_tagged:degree", "undergraduate", "undergraduate", False),
        ("c2", "rule_tagged", "rule_tagged:degree", "master", "doctoral", True),
        ("c3", "rule_unconditioned", "rule_unconditioned:none", "master", "master", False),
        ("c4", "rule_unconditioned", "rule_unconditioned:none", None, "doctoral", False),
    ]
    records = [
        {
            "chunk_id": chunk_id,
            "text": chunk_id,
            "tag_bucket": bucket,
            "condition_status": "conditioned" if predicted else "unconditioned",
            "_campus": "seoul",
            "_heading_path": [],
            "applicability": _condition("seoul", predicted, applicant=applicant),
        }
        for chunk_id, bucket, _, predicted, _, applicant in rows
    ]
    references = [_reference(chunk_id, reference) for chunk_id, _, _, _, reference, _ in rows]
    partition = {bucket: 0 for bucket in BUCKETS}
    partition.update(rule_tagged=6, rule_unconditioned=4)
    metadata = {
        "index_id": "weighted",
        "seed": 1,
        "chunk_ids": [row[0] for row in rows],
        "chunks": {
            chunk_id: {"bucket": bucket, "campus": "seoul", "stratum": stratum}
            for chunk_id, bucket, stratum, *_ in rows
        },
        "bucket_partition": partition,
        "design": {
            "name": "cue",
            "minimums": {"visa": 0, "student_type": 0, "degree": 0},
            "strata": {
                "rule_tagged:degree": {
                    "bucket": "rule_tagged", "cue": "degree", "N_h": 6, "n_h": 2,
                },
                "rule_unconditioned:none": {
                    "bucket": "rule_unconditioned", "cue": "none", "N_h": 4, "n_h": 2,
                },
            },
        },
    }
    return records, references, metadata


def _sampling_index() -> Database:
    mongo = mongomock.MongoClient()["r5-like"]
    db = Database(mongo, None, "unused", "synthetic_r5")  # type: ignore[arg-type]
    for campus in ("seoul", "erica"):
        db.documents.insert_one(
            {
                "doc_id": f"doc-{campus}",
                "title": "International guide",
                "source_uri": f"https://example.test/{campus}",
                "metadata": {"site": campus, "post_date": "2026-11-11"},
            }
        )
    texts = {
        "visa": "D-2 visa information",
        "student_type": "Exchange student information",
        "degree": "Undergraduate course information",
        "none": "General campus information",
    }
    layout = (("visa", 40), ("student_type", 40), ("degree", 40), ("none", 80))
    buckets = ("rule_tagged", "rule_unconditioned", "rule_cue_unknown")
    number = 0
    for cue, count in layout:
        for offset in range(count):
            campus = "erica" if offset % 2 == 0 else "seoul"
            bucket = buckets[offset % len(buckets)]
            db.chunks.insert_one(
                {
                    "chunk_id": f"c{number:03d}",
                    "doc_id": f"doc-{campus}",
                    "text": texts[cue],
                    "section": "Eligibility",
                    "heading_path": ["Eligibility"],
                    "applicability": _condition(campus),
                    "tag_bucket": bucket,
                    "condition_status": "unknown" if bucket == "rule_cue_unknown" else "unconditioned",
                }
            )
            number += 1
    partition = {bucket: db.chunks.count_documents({"tag_bucket": bucket}) for bucket in BUCKETS}
    db.save_manifest({"applicability": {"partition": partition}})
    return db


def test_cue_sample_meets_minimums_is_seeded_and_excludes_both_samples(tmp_path, monkeypatch, capsys):
    db = _sampling_index()
    exclusions = []
    excluded_ids = set()
    for name, chunk_ids in (("M1", [f"c{i:03d}" for i in range(10)]), ("M2", [f"c{i:03d}" for i in range(40, 50)])):
        path = tmp_path / name / "sample_meta.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"chunk_ids": chunk_ids}), encoding="utf-8")
        exclusions.append(path)
        excluded_ids.update(chunk_ids)
    monkeypatch.setattr(auto_audit, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(auto_audit, "connect_index", lambda index_id: db)

    common = [
        "sample", "--index-id", db.index_id, "--design", "cue", "--n", "100",
        "--min-cue", "visa=20", "--min-cue", "student_type=20", "--min-cue", "degree=20",
        "--exclude", str(exclusions[0]), "--exclude", str(exclusions[1]),
    ]
    assert main([*common, "--out", "first"]) == 0
    assert main([*common, "--out", "second"]) == 0

    root = tmp_path / "results" / "tag_audit" / db.index_id
    first = json.loads((root / "first" / "sample_meta.json").read_text(encoding="utf-8"))
    second = json.loads((root / "second" / "sample_meta.json").read_text(encoding="utf-8"))
    assert first["chunk_ids"] == second["chunk_ids"]
    assert len(first["chunk_ids"]) == 100
    assert not set(first["chunk_ids"]) & excluded_ids
    assert all(first["achieved_strata"]["by_cue"][cue] >= 20 for cue in ("visa", "student_type", "degree"))
    assert sum(values["N_h"] for values in first["design"]["strata"].values()) == 180
    assert sum(values["n_h"] for values in first["design"]["strata"].values()) == 100
    assert all("stratum" in values for values in first["chunks"].values())
    for stratum, values in first["design"]["strata"].items():
        if values["n_h"]:
            campuses = Counter(
                chunk["campus"] for chunk in first["chunks"].values() if chunk["stratum"] == stratum
            )
            assert campuses["erica"] >= math.ceil(values["n_h"] * 0.3)
    output = capsys.readouterr().out
    assert all(f'"{cue}"' in output for cue in ("visa", "student_type", "degree"))


def test_cue_precedence_uses_text_title_and_heading_without_predictions():
    row = {
        "text": "Exchange and undergraduate students",
        "_title": "D-2 information",
        "_heading_path": ["Graduate school"],
        "applicability": {"constraints": {"visa": ["d2"]}},
    }
    assert cue_name(row) == "visa"
    row["_title"] = "General information"
    assert cue_name(row) == "student_type"
    row["text"] = "General information"
    assert cue_name(row) == "degree"


def test_two_stratum_weighted_precision_recall_kish_and_applicant_errors():
    """Weights 3,3,2,2 give TP=5, FP=3 and FN=5.

    Weighted precision is 5/8 with n_eff=8^2/(3^2+3^2+2^2)=64/22.
    Weighted recall is 5/10 with n_eff=10^2/(3^2+3^2+2^2+2^2)=100/26.
    The applicant chunk has the weight-3 FP and one of the two FNs, so its
    weighted FN share is 3/(3+2)=3/5.
    """
    records, references, metadata = _design_case()

    scores = score_comparison(records, references, metadata)
    degree = scores["per_attribute"]["degree_level"]
    precision_n_eff = 64 / 22
    recall_n_eff = 100 / 26

    assert (degree["tp"], degree["fp"], degree["fn"]) == pytest.approx((5, 3, 5))
    assert degree["precision"] == pytest.approx(5 / 8)
    assert degree["recall"] == pytest.approx(1 / 2)
    assert degree["weighted_recall"] == pytest.approx(1 / 2)
    assert degree["effective_sample_size"]["precision"] == pytest.approx(precision_n_eff)
    assert degree["effective_sample_size"]["recall"] == pytest.approx(recall_n_eff)
    assert degree["precision_ci"] == pytest.approx(wilson_interval(5 / 8 * precision_n_eff, precision_n_eff))
    assert degree["recall_ci"] == pytest.approx(wilson_interval(1 / 2 * recall_n_eff, recall_n_eff))
    assert degree["unweighted"]["tp"] == 2
    assert degree["unweighted"]["precision"] == pytest.approx(2 / 3)
    assert degree["unweighted"]["recall"] == pytest.approx(1 / 2)
    errors = scores["applicant_chunk_degree_errors"]
    assert errors["fp"] == {"count": 1, "total": 1, "weighted_share": 1.0}
    assert errors["fn"]["count"] == 1
    assert errors["fn"]["total"] == 2
    assert errors["fn"]["weighted_share"] == pytest.approx(3 / 5)
    markdown = scores_markdown(scores)
    assert "Design-weighted values" in markdown
    assert "Unweighted sample values" in markdown
    assert "Degree-level errors in applicant-tagged chunks" in markdown


def test_three_folder_report_uses_labels_and_marks_last_as_gate(tmp_path):
    records, references, metadata = _design_case()
    folders = []
    for name in ("dev-150", "dev-100", "test-100"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "scores_final.json").write_text(
            json.dumps(score_comparison(records, references, metadata)),
            encoding="utf-8",
        )
        folders.append(folder)
    destination = tmp_path / "three-way.md"

    assert main([
        "report", "--side-by-side", *(str(folder) for folder in folders),
        "--label", "dev-150", "--label", "dev-100", "--label", "test-100",
        "--to", str(destination),
    ]) == 0

    report = destination.read_text(encoding="utf-8")
    assert "dev-150:" in report
    assert "dev-100:" in report
    assert "test-100 (gate sample):" in report
    assert "| Attribute | dev-150 occurrences" in report
    assert "## Degree-level errors in applicant-tagged chunks" in report
