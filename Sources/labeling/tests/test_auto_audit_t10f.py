from __future__ import annotations

import json
from collections import Counter

import pytest

import labeling.auto_audit as auto_audit
from labeling.audit_tags import BUCKETS, wilson_interval
from labeling.auto_audit import LIMITATION, main, sample_records, score_comparison


def _condition(campus: str, degree: str | None = None) -> dict:
    constraints = {"degree_level": [degree]} if degree else {}
    return {
        "constraints": constraints,
        "any_of": [],
        "scope": "campus",
        "campus": [campus],
        "effective_term": None,
        "extraction_method": {
            "campus": "site_default",
            "scope": "rule",
            **({"degree_level": "rule"} if degree else {}),
        },
        "evidence": {},
    }


def _reference(chunk_id: str, campus: str, degree: str | None) -> dict:
    return {
        "chunk_id": chunk_id,
        "constraints": {"degree_level": [degree]} if degree else {},
        "any_of": [],
        "scope": "campus",
        "campus": [campus],
        "effective_term": None,
    }


def _five_chunk_case() -> tuple[list[dict], list[dict], dict]:
    rows = [
        ("c1", "rule_tagged", "conditioned", "undergraduate", "undergraduate"),
        ("c2", "rule_tagged", "conditioned", "master", "doctoral"),
        ("c3", "rule_unconditioned", "unconditioned", None, "master"),
        ("c4", "rule_cue_unknown", "unknown", None, "undergraduate"),
        ("c5", "rule_cue_unknown", "unknown", None, "doctoral"),
    ]
    records = [
        {
            "chunk_id": chunk_id,
            "text": chunk_id,
            "tag_bucket": bucket,
            "condition_status": status,
            "_campus": "seoul",
            "_heading_path": [],
            "applicability": _condition("seoul", predicted),
        }
        for chunk_id, bucket, status, predicted, _ in rows
    ]
    references = [
        _reference(chunk_id, "seoul", reference)
        for chunk_id, _, _, _, reference in rows
    ]
    partition = {bucket: 0 for bucket in BUCKETS}
    partition.update(rule_tagged=20, rule_unconditioned=30, rule_cue_unknown=50)
    metadata = {
        "index_id": "five",
        "seed": 1,
        "chunk_ids": [row["chunk_id"] for row in records],
        "chunks": {
            row["chunk_id"]: {"bucket": row["tag_bucket"], "campus": row["_campus"]}
            for row in records
        },
        "bucket_partition": partition,
    }
    return records, references, metadata


def test_resolved_coverage_recall_and_strict_recall_are_hand_computed():
    """Five degree references include two unknown chunks.

    The three resolved chunks give TP=1, FP=1, FN=2: coverage=3/5,
    resolved precision=1/2, and resolved recall=1/3. Both unknown references
    are strict misses, so strict recall=1/5. Bucket weights are 10, 30, and
    25, giving resolved weighted recall=10/50 and strict weighted recall=10/100.
    """
    records, references, metadata = _five_chunk_case()

    scores = score_comparison(records, references, metadata)
    degree = scores["per_attribute"]["degree_level"]

    assert degree["occurrences"] == 5
    assert degree["resolved_occurrences"] == 3
    assert degree["coverage"] == pytest.approx(3 / 5)
    assert degree["coverage_ci"] == pytest.approx(wilson_interval(3, 5))
    assert (degree["tp"], degree["fp"], degree["fn"]) == (1, 1, 2)
    assert degree["precision"] == pytest.approx(1 / 2)
    assert degree["recall"] == pytest.approx(1 / 3)
    assert degree["weighted_recall"] == pytest.approx(1 / 5)
    assert (degree["strict_tp"], degree["strict_fn"]) == (1, 4)
    assert degree["strict_recall"] == pytest.approx(1 / 5)
    assert degree["strict_weighted_recall"] == pytest.approx(1 / 10)
    assert degree["gated"] is True
    assert scores["g2"] == {"passed": False, "failing_attributes": ["degree_level"]}

    campus = scores["per_attribute"]["campus"]
    assert campus["coverage"] == 1
    assert campus["recall"] == 1
    assert campus["strict_recall"] == 1


def test_unknown_share_estimate_and_interval_are_scaled_from_the_sample():
    records, references, metadata = _five_chunk_case()
    references[-1]["constraints"] = {}

    unknown = score_comparison(records, references, metadata)["unknown_share"]

    assert unknown["sampled_unknown_chunks"] == 2
    assert unknown["reference_conditioned_chunks"] == 1
    assert unknown["share"] == pytest.approx(1 / 2)
    assert unknown["share_ci"] == pytest.approx(wilson_interval(1, 2))
    assert unknown["index_unknown_chunks"] == 50
    assert unknown["estimated_conditioned_chunks"] == pytest.approx(25)
    assert unknown["estimated_conditioned_chunks_ci"] == pytest.approx(
        [bound * 50 for bound in wilson_interval(1, 2)]
    )
    assert unknown["top_attributes"] == {"degree_level": 1}


def test_quota_overrides_the_scaled_default_exactly():
    layout = {"rule_tagged": 70, "rule_unconditioned": 40, "rule_cue_unknown": 60}
    records = []
    number = 0
    for bucket, count in layout.items():
        for offset in range(count):
            records.append(
                {
                    "chunk_id": f"c{number:03d}",
                    "tag_bucket": bucket,
                    "condition_status": "unknown" if bucket == "rule_cue_unknown" else "unconditioned",
                    "_campus": "erica" if offset % 2 else "seoul",
                    "text": f"chunk {number}",
                    "applicability": _condition("erica" if offset % 2 else "seoul"),
                }
            )
            number += 1

    selected, targets = sample_records(records, n=100, quotas={"rule_cue_unknown": 30})

    assert targets["rule_cue_unknown"] == 30
    assert Counter(row["tag_bucket"] for row in selected)["rule_cue_unknown"] == 30
    assert len(selected) == 100


def test_report_side_by_side_reads_two_final_folders(tmp_path, capsys):
    records, references, metadata = _five_chunk_case()
    scores_a = score_comparison(records, references, metadata)
    references[-1]["constraints"] = {}
    scores_b = score_comparison(records, references, metadata)
    folder_a, folder_b = tmp_path / "old", tmp_path / "fresh"
    folder_a.mkdir()
    folder_b.mkdir()
    (folder_a / "scores_final.json").write_text(json.dumps(scores_a), encoding="utf-8")
    (folder_b / "scores_final.json").write_text(json.dumps(scores_b), encoding="utf-8")
    destination = tmp_path / "g2b.md"

    assert main([
        "report", "--side-by-side", str(folder_a), str(folder_b), "--to", str(destination)
    ]) == 0

    report = destination.read_text(encoding="utf-8")
    assert report.startswith(LIMITATION)
    assert "| Attribute | A occurrences | A coverage" in report
    assert "| degree_level | 5 |" in report
    assert "## Unknown-condition estimate" in report
    assert "| A | 2 | 2 |" in report
    assert "| B | 2 | 1 |" in report
    assert f"Wrote side-by-side report to {destination}" in capsys.readouterr().out


def test_quota_parser_accepts_repeatable_values_and_rejects_duplicates():
    args = auto_audit.build_parser().parse_args(
        ["sample", "--index-id", "r4", "--quota", "rule_cue_unknown=30", "--quota", "rule_tagged=40"]
    )
    assert auto_audit._quotas(args.quota) == {"rule_cue_unknown": 30, "rule_tagged": 40}
    with pytest.raises(auto_audit.AuditError, match="Duplicate --quota"):
        auto_audit._quotas([("rule_tagged", 1), ("rule_tagged", 2)])
