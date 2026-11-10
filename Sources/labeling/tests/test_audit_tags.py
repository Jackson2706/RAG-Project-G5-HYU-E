from __future__ import annotations

import csv
import json
from collections import Counter

import pytest

from labeling.audit_tags import (
    ATTRIBUTES,
    BUCKETS,
    CSV_COLUMNS,
    AuditError,
    SheetValidationError,
    audit_records,
    bucket_weighted_recall,
    csv_row,
    frequency_data,
    main,
    manifest_bucket_partition,
    sample_records,
    sample_metadata,
    score_csv,
    score_rows,
    scores_markdown,
    sidecar_path,
    stratum_counts,
    wilson_interval,
    write_sample_csv,
)


def test_sampling_meets_floors_is_seeded_and_has_ordered_columns(synthetic_index, tmp_path):
    db, snapshots = synthetic_index
    records = audit_records(db, snapshots)
    first = sample_records(records, seed=20261110)
    second = sample_records(list(reversed(records)), seed=20261110)

    assert [row["chunk_id"] for row in first] == [row["chunk_id"] for row in second]
    counts = stratum_counts(first)
    assert counts["campus_seoul"] == counts["campus_erica"] == 25
    assert counts["conditioned"] >= 20
    assert counts["table_row"] >= 5
    assert counts["rule_unconditioned"] >= 8
    assert counts["llm_unconditioned"] >= 5
    assert counts["llm_rejected"] >= 3
    assert counts["llm_extracted"] >= 10
    assert counts["llm_topik_level"] >= 6

    path = tmp_path / "audit.csv"
    metadata = sample_metadata(db.index_id, 20261110, first, manifest_bucket_partition(db))
    write_sample_csv(first, path, metadata)
    with path.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == list(CSV_COLUMNS)
    assert json.loads(sidecar_path(path).read_text(encoding="utf-8")) == metadata
    assert metadata["n"] == 50
    assert metadata["stratum_counts"]["llm_topik_level"] >= 6
    assert set(metadata["bucket_partition"]) == set(BUCKETS)


def test_sampling_fails_clearly_when_a_stratum_is_too_small(synthetic_index):
    db, snapshots = synthetic_index
    records = audit_records(db, snapshots)
    for row in records:
        if row["tag_bucket"] == "llm_rejected":
            row["tag_bucket"] = "llm_unconditioned"
            row["condition_status"] = "unconditioned"

    with pytest.raises(AuditError, match=r"llm_rejected floor: need 3"):
        sample_records(records)


def test_sample_refuses_to_overwrite(synthetic_index, tmp_path):
    db, snapshots = synthetic_index
    path = tmp_path / "audit.csv"
    sample = sample_records(audit_records(db, snapshots))
    metadata = sample_metadata(db.index_id, 20261110, sample, manifest_bucket_partition(db))
    write_sample_csv(sample, path, metadata)

    with pytest.raises(AuditError, match="Refusing to overwrite"):
        write_sample_csv(sample, path, metadata)


def _review_row(campus: str, bucket: str, *, pred: str = "", method: str = "",
                correct: str = "", wrong: str = "", missed: str = "") -> dict[str, str]:
    row = {column: "" for column in CSV_COLUMNS}
    row.update(
        chunk_id=f"{campus}-{bucket}",
        campus=campus,
        tag_bucket=bucket,
        condition_status="conditioned" if bucket.endswith("_tagged") else "unconditioned",
        reviewer="human:JT",
        campus_pred=campus,
        campus_method="site_default",
        campus_correct=campus,
        degree_level_pred=pred,
        degree_level_method=method,
        degree_level_correct=correct,
        degree_level_wrong=wrong,
        degree_level_missed=missed,
    )
    return row


def _write_review_sheet(path, rows, bucket_partition=None, write_sidecar=True):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(row for _, row in rows)
    if write_sidecar:
        sampled = Counter(row["tag_bucket"] for _, row in rows)
        partition = bucket_partition or {bucket: sampled[bucket] for bucket in BUCKETS}
        sidecar_path(path).write_text(
            json.dumps({"index_id": "synthetic", "seed": 1, "n": len(rows), "bucket_partition": partition}),
            encoding="utf-8",
        )


def test_scoring_matches_hand_computation_and_splits(tmp_path):
    """Four rows give degree TP=2, FP=1, FN=3: P=2/3 and R=2/5.

    Rule has TP=1, FP=1, FN=1. LLM has TP=1, FP=0, FN=2; the final FN belongs
    to its empty ``llm_unconditioned`` row. Bucket counts are the same partition.
    """
    rows = [
        (2, _review_row("seoul", "rule_tagged", pred="undergraduate", method="rule", correct="undergraduate")),
        (3, _review_row("seoul", "rule_tagged", pred="master", method="rule", wrong="master", missed="doctoral")),
        (4, _review_row("erica", "llm_tagged", pred="undergraduate", method="llm", correct="undergraduate", missed="master")),
        (5, _review_row("erica", "llm_unconditioned", missed="doctoral")),
    ]

    path = tmp_path / "four_rows.csv"
    _write_review_sheet(path, rows)
    scores = score_csv(path)
    degree = scores["per_attribute"]["degree_level"]
    assert degree["tp"] == 2
    assert degree["fp"] == 1
    assert degree["fn"] == 3
    assert degree["precision"] == pytest.approx(2 / 3)
    assert degree["recall"] == pytest.approx(2 / 5)
    assert degree["weighted_recall"] == pytest.approx(2 / 5)
    assert degree["occurrences"] == 4
    assert not degree["gated"]
    assert degree["precision_ci"] == pytest.approx(wilson_interval(2, 3))
    assert degree["recall_ci"] == pytest.approx(wilson_interval(2, 5))
    assert scores["by_method"]["rule"]["degree_level"]["tp"] == 1
    assert scores["by_method"]["rule"]["degree_level"]["fp"] == 1
    assert scores["by_method"]["rule"]["degree_level"]["fn"] == 1
    assert scores["by_method"]["llm"]["degree_level"]["tp"] == 1
    assert scores["by_method"]["llm"]["degree_level"]["fn"] == 2
    assert scores["by_bucket"]["llm_unconditioned"]["degree_level"]["fn"] == 1
    assert scores["by_bucket"]["rule_tagged"]["degree_level"]["fp"] == 1
    assert scores["per_attribute"]["visa"]["precision"] is None
    assert scores["per_attribute"]["visa"]["recall"] is None


def test_wilson_interval_matches_hand_computed_example():
    assert wilson_interval(8, 10) == pytest.approx([0.490, 0.943], abs=0.0005)
    assert wilson_interval(0, 0) is None


def test_bucket_weighted_recall_matches_hand_computed_sheet():
    """A: N=80, n=8, TP/FN=4/4; B: N=20, n=10, TP/FN=9/1.

    The weights are 10 and 2, so recall_w=(10*4+2*9)/(10*8+2*10)=0.58.
    Raw recall is 13/18.
    """
    rows = []
    for index in range(8):
        kwargs = {"pred": "undergraduate", "method": "rule", "correct": "undergraduate"}
        if index >= 4:
            kwargs = {"missed": "master"}
        rows.append((index + 2, _review_row("seoul", "rule_tagged", **kwargs)))
    for index in range(10):
        kwargs = {"pred": "undergraduate", "method": "llm", "correct": "undergraduate"}
        if index == 9:
            kwargs = {"missed": "master"}
        rows.append((index + 10, _review_row("erica", "llm_tagged", **kwargs)))
    partition = {bucket: 0 for bucket in BUCKETS}
    partition.update(rule_tagged=80, llm_tagged=20, llm_errors=5)

    scores = score_rows(rows, partition)
    degree = scores["per_attribute"]["degree_level"]
    assert degree["recall"] == pytest.approx(13 / 18)
    assert degree["weighted_recall"] == pytest.approx(0.58)
    assert degree["weighted_recall_ci"] == pytest.approx(wilson_interval(0.58 * 18, 18))
    assert bucket_weighted_recall(
        {"rule_tagged": {"tp": 4, "fn": 4}, "llm_tagged": {"tp": 9, "fn": 1}},
        partition,
        {"rule_tagged": 8, "llm_tagged": 10},
    ) == pytest.approx(0.58)
    assert scores["not_sampled_buckets"] == ["llm_errors"]
    assert scores["g2"]["failing_attributes"] == ["degree_level"]


def test_score_requires_metadata_sidecar(tmp_path):
    row = _review_row("seoul", "rule_tagged", pred="undergraduate", method="rule", correct="undergraduate")
    path = tmp_path / "missing_meta.csv"
    _write_review_sheet(path, [(2, row)], write_sidecar=False)

    with pytest.raises(AuditError, match=r"metadata sidecar not found: .*missing_meta\.meta\.json"):
        score_csv(path)


def test_audience_is_validated_and_free_text_is_reported():
    invalid = _review_row("seoul", "rule_tagged")
    invalid["audience"] = "visitor"
    with pytest.raises(SheetValidationError, match="row 2 audience: values outside the allowed list"):
        score_rows([(2, invalid)])

    valid = _review_row("seoul", "rule_tagged")
    valid["audience"] = "applicant|enrolled"
    valid["out_of_vocabulary_condition"] = "GPA >= 3.0"
    scores = score_rows([(2, valid)])
    assert scores["audience_distribution"] == {"applicant": 1, "admitted": 0, "enrolled": 1}
    assert scores["out_of_vocabulary_conditions"] == {"GPA >= 3.0": 1}
    markdown = scores_markdown(scores)
    assert "| GPA >= 3.0 | 1 |" in markdown
    assert "| applicant | 1 |" in markdown
    assert "Precision (95% CI)" in markdown


def test_scoring_violation_exits_two_and_names_row_and_attribute(tmp_path, capsys):
    row = _review_row("seoul", "rule_tagged", pred="undergraduate", method="rule")
    path = tmp_path / "bad.csv"
    _write_review_sheet(path, [(2, row)])

    assert main(["score", "--csv", str(path), "--out", str(tmp_path / "out")]) == 2
    assert "row 2 degree_level" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
    with pytest.raises(SheetValidationError, match="row 2 degree_level"):
        score_rows([(2, row)])


def test_g2_uses_five_occurrences_and_reports_unknown_misses():
    rows = [
        (number, _review_row("seoul", "rule_tagged", pred="undergraduate", method="rule", correct="undergraduate"))
        for number in range(2, 7)
    ]
    scores = score_rows(rows)
    assert scores["per_attribute"]["degree_level"]["gated"]
    assert scores["g2"] == {"passed": True, "failing_attributes": []}

    rows[0][1]["degree_level_missed"] = "master"
    rows[1][1]["degree_level_missed"] = "master"
    unknown = _review_row("erica", "llm_rejected", missed="doctoral")
    scores = score_rows([*rows, (7, unknown)])
    assert scores["g2"]["failing_attributes"] == ["degree_level"]
    assert scores["unknown_chunks"] == {"count": 1, "with_any_missed": 1}


def test_frequency_counts_methods_campuses_and_unseen_values(synthetic_index):
    db, _ = synthetic_index
    report = frequency_data(db)
    rows = {(row["attribute"], row["value"]): row for row in report["frequencies"]}

    assert report["chunks"] == 80
    assert rows[("degree_level", "undergraduate")]["count"] == 24
    assert rows[("degree_level", "undergraduate")]["by_method"] == {"rule": 24, "llm": 0}
    assert rows[("student_type", "exchange")]["count"] == 16
    assert rows[("student_type", "exchange")]["by_method"] == {"rule": 0, "llm": 16}
    assert rows[("campus", "seoul")]["by_campus"] == {"seoul": 40, "erica": 0}
    assert "student_type=short_term" in report["never_seen"]
    assert report["top_requirements"][0] == {"phrase": "GPA 3.0", "count": 12}


def test_csv_row_leaves_review_cells_empty(synthetic_index):
    db, snapshots = synthetic_index
    row = csv_row(audit_records(db, snapshots)[0])
    assert list(row)[:8] == list(CSV_COLUMNS[:8])
    assert all(row[f"{attribute}_{field}"] == "" for attribute in ATTRIBUTES for field in ("correct", "wrong", "missed"))
