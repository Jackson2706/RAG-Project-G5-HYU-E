from __future__ import annotations

import csv

import pytest

from labeling.audit_tags import (
    ATTRIBUTES,
    CSV_COLUMNS,
    AuditError,
    SheetValidationError,
    audit_records,
    csv_row,
    frequency_data,
    main,
    sample_records,
    score_csv,
    score_rows,
    stratum_counts,
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

    path = tmp_path / "audit.csv"
    write_sample_csv(first, path)
    with path.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == list(CSV_COLUMNS)


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
    write_sample_csv(sample, path)

    with pytest.raises(AuditError, match="Refusing to overwrite"):
        write_sample_csv(sample, path)


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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(row for _, row in rows)
    scores = score_csv(path)
    degree = scores["per_attribute"]["degree_level"]
    assert degree == {"tp": 2, "fp": 1, "fn": 3, "precision": pytest.approx(2 / 3),
                      "recall": pytest.approx(2 / 5), "occurrences": 4, "gated": False}
    assert scores["by_method"]["rule"]["degree_level"]["tp"] == 1
    assert scores["by_method"]["rule"]["degree_level"]["fp"] == 1
    assert scores["by_method"]["rule"]["degree_level"]["fn"] == 1
    assert scores["by_method"]["llm"]["degree_level"]["tp"] == 1
    assert scores["by_method"]["llm"]["degree_level"]["fn"] == 2
    assert scores["by_bucket"]["llm_unconditioned"]["degree_level"]["fn"] == 1
    assert scores["by_bucket"]["rule_tagged"]["degree_level"]["fp"] == 1
    assert scores["per_attribute"]["visa"]["precision"] is None
    assert scores["per_attribute"]["visa"]["recall"] is None


def test_scoring_violation_exits_two_and_names_row_and_attribute(tmp_path, capsys):
    row = _review_row("seoul", "rule_tagged", pred="undergraduate", method="rule")
    path = tmp_path / "bad.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerow(row)

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
