"""Sample, score, and count AAES applicability tags.

Run from ``Sources/``::

    python -m labeling.audit_tags sample --index-id hyu_20261110_97dc1269_r1 --n 50 --seed 20261110
    python -m labeling.audit_tags score --csv ../Report/notes/tag_audit.csv
    python -m labeling.audit_tags frequency --index-id hyu_20261110_97dc1269_r1
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from app.config import REPORT_DIR, RESULTS_DIR, get_settings
from app.database import Database
from app.rag.applicability import METHODS, TERM_RE, VOCABULARY
from app.rag.snapshot import snapshot_dir

INDEX_ID = "hyu_20261110_97dc1269_r1"
ATTRIBUTES = (
    "degree_level",
    "year",
    "student_type",
    "visa",
    "topik_level",
    "english_track",
    "academic_status",
    "campus",
    "effective_term",
)
BUCKETS = (
    "rule_tagged",
    "rule_unconditioned",
    "llm_tagged",
    "llm_unconditioned",
    "llm_rejected",
    "llm_errors",
)
BASE_COLUMNS = (
    "chunk_id",
    "campus",
    "source_uri",
    "kind",
    "tag_bucket",
    "condition_status",
    "section",
    "text",
)
AUDIT_COLUMNS = tuple(
    column
    for attribute in ATTRIBUTES
    for column in (
        f"{attribute}_pred",
        f"{attribute}_method",
        f"{attribute}_correct",
        f"{attribute}_wrong",
        f"{attribute}_missed",
    )
)
AUDIENCES = ("applicant", "admitted", "enrolled")
CSV_COLUMNS = (
    *BASE_COLUMNS,
    *AUDIT_COLUMNS,
    "out_of_vocabulary_condition",
    "audience",
    "reviewer",
    "notes",
)


class AuditError(ValueError):
    """An audit command cannot produce a valid result."""


class SheetValidationError(AuditError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def _values(condition: dict, attribute: str) -> list[str]:
    if attribute == "campus":
        return condition.get("campus") or []
    if attribute == "effective_term":
        return [condition["effective_term"]] if condition.get("effective_term") else []
    return (condition.get("constraints") or {}).get(attribute) or []


def _method_family(method: str | None, bucket: str | None = None) -> str:
    if method == "llm" or (not method and (bucket or "").startswith("llm_")):
        return "llm"
    return "rule"


def _document_campus(document: dict) -> str:
    metadata = document.get("metadata") or {}
    campus = metadata.get("site") or metadata.get("campus") or document.get("site")
    if isinstance(campus, list):
        campus = campus[0] if len(campus) == 1 else None
    if campus not in VOCABULARY["campus"]:
        raise AuditError(f"Document {document.get('doc_id')} has no Seoul/ERICA site metadata")
    return campus


def load_snapshot_rows(db: Database) -> list[dict]:
    manifest = db.get_manifest() or {}
    snapshot_id = manifest.get("snapshot_id")
    if not snapshot_id:
        raise AuditError(f"Index {db.index_id} manifest has no snapshot_id")
    path = snapshot_dir(snapshot_id) / "documents.jsonl"
    if not path.exists():
        raise AuditError(f"Snapshot file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _chunk_kind(chunk: dict, snapshot: dict) -> str:
    kinds_by_offset = {
        (span["char_start"], span["char_end"]): span["kind"]
        for span in snapshot.get("spans", [])
    }
    offsets = [tuple(pair) for pair in chunk.get("source_spans") or []]
    kinds = [kinds_by_offset.get(offset) for offset in offsets]
    if not kinds or any(kind is None for kind in kinds):
        raise AuditError(f"Chunk {chunk.get('chunk_id')} has source_spans absent from its snapshot row")
    return kinds[0] if len(set(kinds)) == 1 else "mixed"


def audit_records(db: Database, snapshot_rows: list[dict]) -> list[dict]:
    documents = {
        document["doc_id"]: document
        for document in db.documents.find({}, {"_id": 0})
    }
    snapshots = {row["source_uri"]: row for row in snapshot_rows}
    records = []
    for chunk in db.chunks.find({}, {"_id": 0}):
        document = documents.get(chunk.get("doc_id"))
        if not document:
            raise AuditError(f"Chunk {chunk.get('chunk_id')} has no document")
        snapshot = snapshots.get(document.get("source_uri"))
        if not snapshot:
            raise AuditError(f"Document {document.get('doc_id')} has no snapshot row")
        records.append(
            {
                **chunk,
                "_campus": _document_campus(document),
                "_source_uri": document["source_uri"],
                "_kind": _chunk_kind(chunk, snapshot),
            }
        )
    return sorted(records, key=lambda record: record["chunk_id"])


FLOORS: tuple[tuple[str, int, Callable[[dict], bool]], ...] = (
    ("llm_extracted", 10, lambda row: "llm" in (row.get("applicability", {}).get("extraction_method") or {}).values()),
    ("llm_topik_level", 6, lambda row: (row.get("applicability", {}).get("extraction_method") or {}).get("topik_level") == "llm"),
    ("table_row", 5, lambda row: row["_kind"] == "table_row"),
    ("conditioned", 20, lambda row: row.get("condition_status") == "conditioned"),
    ("rule_unconditioned", 8, lambda row: row.get("tag_bucket") == "rule_unconditioned"),
    ("llm_unconditioned", 5, lambda row: row.get("tag_bucket") == "llm_unconditioned"),
    ("llm_rejected", 3, lambda row: row.get("tag_bucket") == "llm_rejected"),
)


def stratum_counts(records: list[dict]) -> dict[str, int]:
    counts = {name: sum(predicate(row) for row in records) for name, _, predicate in FLOORS}
    counts.update({f"campus_{campus}": sum(row["_campus"] == campus for row in records) for campus in VOCABULARY["campus"]})
    return counts


def sample_records(records: list[dict], n: int = 50, seed: int = 20261110) -> list[dict]:
    if n != 50:
        raise AuditError("The T10 audit has fixed floors of 25 chunks per campus; --n must be 50")
    records = sorted(records, key=lambda record: record["chunk_id"])
    rng = random.Random(seed)
    selected: list[dict] = []
    selected_ids: set[str] = set()
    campus_counts = Counter()

    def add_for(name: str, target: int, predicate: Callable[[dict], bool]) -> None:
        have = sum(predicate(row) for row in selected)
        candidates = [
            row
            for row in records
            if row["chunk_id"] not in selected_ids and predicate(row) and campus_counts[row["_campus"]] < 25
        ]
        rng.shuffle(candidates)
        needed = max(0, target - have)
        for row in candidates:
            if needed == 0:
                break
            if campus_counts[row["_campus"]] >= 25:
                continue
            selected.append(row)
            selected_ids.add(row["chunk_id"])
            campus_counts[row["_campus"]] += 1
            needed -= 1
        achieved = sum(predicate(row) for row in selected)
        if achieved < target:
            available = sum(predicate(row) for row in records)
            raise AuditError(f"Cannot meet {name} floor: need {target}, achieved {achieved} ({available} in index)")

    for name, target, predicate in FLOORS:
        add_for(name, target, predicate)
    for campus in VOCABULARY["campus"]:
        add_for(f"campus_{campus}", 25, lambda row, campus=campus: row["_campus"] == campus)

    if len(selected) != n:
        raise AuditError(f"Sampling floors selected {len(selected)} chunks instead of {n}")
    achieved = stratum_counts(selected)
    for name, target, _ in FLOORS:
        if achieved[name] < target:
            raise AuditError(f"Cannot meet {name} floor: need {target}, achieved {achieved[name]}")
    return sorted(selected, key=lambda record: record["chunk_id"])


def csv_row(record: dict) -> dict[str, str]:
    condition = record.get("applicability") or {}
    methods = condition.get("extraction_method") or {}
    row = {
        "chunk_id": str(record["chunk_id"]),
        "campus": record["_campus"],
        "source_uri": record["_source_uri"],
        "kind": record["_kind"],
        "tag_bucket": record.get("tag_bucket", ""),
        "condition_status": record.get("condition_status", ""),
        "section": record.get("section") or "",
        "text": record.get("text") or "",
        "out_of_vocabulary_condition": "",
        "audience": "",
        "reviewer": "",
        "notes": "",
    }
    for attribute in ATTRIBUTES:
        row[f"{attribute}_pred"] = "|".join(_values(condition, attribute))
        row[f"{attribute}_method"] = methods.get(attribute, "")
        row[f"{attribute}_correct"] = ""
        row[f"{attribute}_wrong"] = ""
        row[f"{attribute}_missed"] = ""
    return row


def sidecar_path(path: Path) -> Path:
    return path.with_suffix(".meta.json")


def manifest_bucket_partition(db: Database) -> dict[str, int]:
    manifest = db.get_manifest() or {}
    partition = (manifest.get("applicability") or {}).get("partition")
    if not isinstance(partition, dict):
        raise AuditError(f"Index {db.index_id} manifest has no applicability.partition")
    missing = [bucket for bucket in BUCKETS if bucket not in partition]
    invalid = [
        bucket
        for bucket in BUCKETS
        if bucket in partition and (not isinstance(partition[bucket], int) or partition[bucket] < 0)
    ]
    if missing or invalid:
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if invalid:
            details.append(f"invalid sizes for {', '.join(invalid)}")
        raise AuditError(f"Index {db.index_id} manifest applicability.partition is incomplete: {'; '.join(details)}")
    return {bucket: partition[bucket] for bucket in BUCKETS}


def sample_metadata(index_id: str, seed: int, records: list[dict], bucket_partition: dict[str, int]) -> dict:
    return {
        "index_id": index_id,
        "seed": seed,
        "n": len(records),
        "stratum_counts": stratum_counts(records),
        "bucket_partition": bucket_partition,
    }


def write_sample_csv(records: list[dict], path: Path, metadata: dict, force: bool = False) -> None:
    meta_path = sidecar_path(path)
    existing = next((candidate for candidate in (path, meta_path) if candidate.exists()), None)
    if existing and not force:
        raise AuditError(f"Refusing to overwrite existing audit file: {existing} (use --force)")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_row(record) for record in records)
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _split(cell: str | None) -> list[str]:
    return [value.strip() for value in (cell or "").split("|") if value.strip()]


def _valid_value(attribute: str, value: str) -> bool:
    return bool(TERM_RE.fullmatch(value)) if attribute == "effective_term" else value in VOCABULARY[attribute]


def read_reviewed_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in CSV_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise SheetValidationError([f"sheet: missing columns: {', '.join(missing)}"])
        return [(number, row) for number, row in enumerate(reader, 2) if (row.get("reviewer") or "").strip()]


def validate_rows(rows: list[tuple[int, dict[str, str]]]) -> list[str]:
    errors = []
    for number, row in rows:
        audience = _split(row.get("audience"))
        invalid_audiences = sorted(value for value in audience if value not in AUDIENCES)
        if invalid_audiences:
            errors.append(f"row {number} audience: values outside the allowed list {invalid_audiences}")
        for attribute in ATTRIBUTES:
            pred = _split(row.get(f"{attribute}_pred"))
            correct = _split(row.get(f"{attribute}_correct"))
            wrong = _split(row.get(f"{attribute}_wrong"))
            missed = _split(row.get(f"{attribute}_missed"))
            for label, values in (("pred", pred), ("correct", correct), ("wrong", wrong), ("missed", missed)):
                duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
                if duplicates:
                    errors.append(f"row {number} {attribute}: duplicate {label} values {duplicates}")
                bad = sorted(value for value in values if not _valid_value(attribute, value))
                if bad:
                    errors.append(f"row {number} {attribute}: values outside the vocabulary {bad}")
            if set(correct) & set(wrong):
                errors.append(f"row {number} {attribute}: a predicted value is both correct and wrong")
            if set(correct) | set(wrong) != set(pred):
                errors.append(f"row {number} {attribute}: correct and wrong must partition pred exactly")
            if set(missed) & set(pred):
                errors.append(f"row {number} {attribute}: missed values must not be predicted")
            method = (row.get(f"{attribute}_method") or "").strip()
            if pred and method not in METHODS:
                errors.append(f"row {number} {attribute}: predicted values need a valid extraction method")
    return errors


def _empty_counts() -> dict[str, Any]:
    return {attribute: {"tp": 0, "fp": 0, "fn": 0, "rows": set()} for attribute in ATTRIBUTES}


def _add(counts: dict, attribute: str, row_number: int, tp: int, fp: int, fn: int) -> None:
    entry = counts[attribute]
    entry["tp"] += tp
    entry["fp"] += fp
    entry["fn"] += fn
    if tp or fp or fn:
        entry["rows"].add(row_number)


def wilson_interval(successes: float, n: int, z: float = 1.96) -> list[float] | None:
    """Return a Wilson score interval for a proportion.

    For 8 successes in 10 trials, the 95% interval is [0.490, 0.943] after
    rounding to three decimals.
    """
    if n == 0:
        return None
    proportion = successes / n
    denominator = 1 + z**2 / n
    center = (proportion + z**2 / (2 * n)) / denominator
    half = z * (proportion * (1 - proportion) / n + z**2 / (4 * n**2)) ** 0.5 / denominator
    return [center - half, center + half]


def bucket_weighted_recall(
    counts_by_bucket: dict[str, dict[str, int]],
    bucket_partition: dict[str, int],
    sample_bucket_counts: dict[str, int],
) -> float | None:
    """Return recall after weighting reviewed buckets back to the index.

    Suppose bucket A has 80 index chunks and 8 reviewed chunks with TP=4,
    FN=4. Bucket B has 20 index chunks and 10 reviewed chunks with TP=9,
    FN=1. Their weights are 10 and 2, so weighted recall is
    (10*4 + 2*9) / (10*8 + 2*10) = 58/100 = 0.58.
    """
    numerator = 0.0
    denominator = 0.0
    for bucket in BUCKETS:
        sampled = sample_bucket_counts.get(bucket, 0)
        if sampled == 0:
            continue
        weight = bucket_partition.get(bucket, 0) / sampled
        entry = counts_by_bucket.get(bucket) or {}
        tp, fn = entry.get("tp", 0), entry.get("fn", 0)
        numerator += weight * tp
        denominator += weight * (tp + fn)
    return numerator / denominator if denominator else None


def _metric_entry(
    entry: dict,
    counts_by_bucket: dict[str, dict],
    bucket_partition: dict[str, int],
    sample_bucket_counts: dict[str, int],
) -> dict:
    tp, fp, fn = entry["tp"], entry["fp"], entry["fn"]
    precision_n, recall_n = tp + fp, tp + fn
    weighted_recall = bucket_weighted_recall(counts_by_bucket, bucket_partition, sample_bucket_counts)
    # shortcut: Wilson on raw n for a weighted proportion; use a bootstrap if the gate is borderline
    weighted_recall_ci = wilson_interval(weighted_recall * recall_n, recall_n) if weighted_recall is not None else None
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / precision_n if precision_n else None,
        "precision_ci": wilson_interval(tp, precision_n),
        "recall": tp / recall_n if recall_n else None,
        "recall_ci": wilson_interval(tp, recall_n),
        "weighted_recall": weighted_recall,
        "weighted_recall_ci": weighted_recall_ci,
        "occurrences": len(entry["rows"]),
        "gated": len(entry["rows"]) >= 5,
    }


def _metrics(
    counts: dict,
    counts_by_bucket: dict[str, dict],
    bucket_partition: dict[str, int],
    sample_bucket_counts: dict[str, int],
) -> dict:
    output = {}
    for attribute, entry in counts.items():
        bucket_entries = {bucket: bucket_counts[attribute] for bucket, bucket_counts in counts_by_bucket.items()}
        output[attribute] = _metric_entry(entry, bucket_entries, bucket_partition, sample_bucket_counts)
    return output


def _method_summary(
    method_counts: dict,
    method_bucket_counts: dict[str, dict],
    bucket_partition: dict[str, int],
    sample_bucket_counts: dict[str, int],
) -> dict:
    entry = {
        key: sum(attribute[key] for attribute in method_counts.values())
        for key in ("tp", "fp", "fn")
    }
    entry["rows"] = {
        (attribute, row_number)
        for attribute, counts in method_counts.items()
        for row_number in counts["rows"]
    }
    bucket_entries = {
        bucket: {
            key: sum(attribute[key] for attribute in counts.values())
            for key in ("tp", "fp", "fn")
        }
        for bucket, counts in method_bucket_counts.items()
    }
    return _metric_entry(entry, bucket_entries, bucket_partition, sample_bucket_counts)


def score_rows(rows: list[tuple[int, dict[str, str]]], bucket_partition: dict[str, int] | None = None) -> dict:
    errors = validate_rows(rows)
    if errors:
        raise SheetValidationError(errors)

    overall = _empty_counts()
    by_method = {method: _empty_counts() for method in ("rule", "llm")}
    by_bucket = {bucket: _empty_counts() for bucket in BUCKETS}
    by_campus = {campus: _empty_counts() for campus in VOCABULARY["campus"]}
    by_method_bucket = {
        method: {bucket: _empty_counts() for bucket in BUCKETS}
        for method in ("rule", "llm")
    }
    by_campus_bucket = {
        campus: {bucket: _empty_counts() for bucket in BUCKETS}
        for campus in VOCABULARY["campus"]
    }
    unknown, unknown_with_missed = 0, 0
    out_of_vocabulary_conditions: Counter[str] = Counter()
    audience_distribution = Counter({audience: 0 for audience in AUDIENCES})
    sample_bucket_counts = Counter(row.get("tag_bucket", "") for _, row in rows)
    if bucket_partition is None:
        bucket_partition = {bucket: sample_bucket_counts[bucket] for bucket in BUCKETS}

    for number, row in rows:
        bucket, campus = row.get("tag_bucket", ""), row.get("campus", "")
        if bucket not in by_bucket:
            raise SheetValidationError([f"row {number} tag_bucket: unknown bucket {bucket!r}"])
        if campus not in by_campus:
            raise SheetValidationError([f"row {number} campus: unknown campus {campus!r}"])
        out_of_vocabulary = (row.get("out_of_vocabulary_condition") or "").strip()
        if out_of_vocabulary:
            out_of_vocabulary_conditions[out_of_vocabulary] += 1
        audience_distribution.update(_split(row.get("audience")))
        row_has_missed = False
        for attribute in ATTRIBUTES:
            correct = _split(row.get(f"{attribute}_correct"))
            wrong = _split(row.get(f"{attribute}_wrong"))
            missed = _split(row.get(f"{attribute}_missed"))
            tp, fp, fn = len(correct), len(wrong), len(missed)
            _add(overall, attribute, number, tp, fp, fn)
            _add(by_bucket[bucket], attribute, number, tp, fp, fn)
            _add(by_campus[campus], attribute, number, tp, fp, fn)
            _add(by_campus_bucket[campus][bucket], attribute, number, tp, fp, fn)
            if tp or fp:
                family = _method_family(row.get(f"{attribute}_method"), bucket)
                _add(by_method[family], attribute, number, tp, fp, 0)
                _add(by_method_bucket[family][bucket], attribute, number, tp, fp, 0)
            if fn:
                family = _method_family(None, bucket)
                _add(by_method[family], attribute, number, 0, 0, fn)
                _add(by_method_bucket[family][bucket], attribute, number, 0, 0, fn)
                row_has_missed = True
        if bucket == "llm_rejected":
            unknown += 1
            unknown_with_missed += row_has_missed

    per_attribute = _metrics(overall, by_bucket, bucket_partition, sample_bucket_counts)
    failing = [
        attribute
        for attribute, metric in per_attribute.items()
        if metric["gated"] and (metric["precision"] is None or metric["precision"] < 0.8
                                or metric["weighted_recall"] is None or metric["weighted_recall"] < 0.7)
    ]
    method_metrics = {
        name: _metrics(counts, by_method_bucket[name], bucket_partition, sample_bucket_counts)
        for name, counts in by_method.items()
    }
    method_summary = {
        name: _method_summary(counts, by_method_bucket[name], bucket_partition, sample_bucket_counts)
        for name, counts in by_method.items()
    }
    for metric in method_summary.values():
        metric["passed"] = (
            metric["precision"] is not None
            and metric["precision"] >= 0.8
            and metric["weighted_recall"] is not None
            and metric["weighted_recall"] >= 0.7
        )
    return {
        "reviewed_rows": len(rows),
        "per_attribute": per_attribute,
        "by_method": method_metrics,
        "by_bucket": {
            name: _metrics(counts, {name: counts}, bucket_partition, sample_bucket_counts)
            for name, counts in by_bucket.items()
        },
        "by_campus": {
            name: _metrics(counts, by_campus_bucket[name], bucket_partition, sample_bucket_counts)
            for name, counts in by_campus.items()
        },
        "method_summary": method_summary,
        "not_sampled_buckets": [
            bucket for bucket in BUCKETS
            if bucket_partition.get(bucket, 0) > 0 and sample_bucket_counts[bucket] == 0
        ],
        "out_of_vocabulary_conditions": dict(sorted(out_of_vocabulary_conditions.items())),
        "audience_distribution": dict(audience_distribution),
        "unknown_chunks": {"count": unknown, "with_any_missed": unknown_with_missed},
        "g2": {"passed": not failing, "failing_attributes": failing},
    }


def read_sample_metadata(path: Path) -> dict:
    meta_path = sidecar_path(path)
    if not meta_path.exists():
        raise AuditError(f"Audit metadata sidecar not found: {meta_path}. Run the sample command first.")
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise AuditError(f"Cannot read audit metadata sidecar {meta_path}: {exc}") from exc
    partition = metadata.get("bucket_partition") if isinstance(metadata, dict) else None
    if not isinstance(partition, dict) or any(
        not isinstance(partition.get(bucket), int) or partition[bucket] < 0 for bucket in BUCKETS
    ):
        raise AuditError(f"Audit metadata sidecar {meta_path} has no valid six-bucket partition")
    return metadata


def score_csv(path: Path) -> dict:
    metadata = read_sample_metadata(path)
    scores = score_rows(read_reviewed_rows(path), metadata["bucket_partition"])
    scores["index_id"] = metadata.get("index_id")
    scores["sample_n"] = metadata.get("n")
    return scores


def _format_metric(value: float | None, interval: list[float] | None) -> str:
    if value is None or interval is None:
        return "null [null]"
    return f"{value:.3f} [{interval[0]:.3f}, {interval[1]:.3f}]"


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _append_metric_table(lines: list[str], attributes: dict, include_gate: bool = False) -> None:
    gate_heading = " | Gated" if include_gate else ""
    gate_rule = "|---" if include_gate else ""
    lines.extend(
        [
            f"| Attribute | TP | FP | FN | Precision (95% CI) | Recall raw (95% CI) | Recall weighted (95% CI) | Occurrences{gate_heading} |",
            f"|---|---:|---:|---:|---:|---:|---:|---:{gate_rule}|",
        ]
    )
    for attribute, metric in attributes.items():
        gate = f" | {'yes' if metric['gated'] else 'no'}" if include_gate else ""
        lines.append(
            f"| {attribute} | {metric['tp']} | {metric['fp']} | {metric['fn']} | "
            f"{_format_metric(metric['precision'], metric['precision_ci'])} | "
            f"{_format_metric(metric['recall'], metric['recall_ci'])} | "
            f"{_format_metric(metric['weighted_recall'], metric['weighted_recall_ci'])} | "
            f"{metric['occurrences']}{gate} |"
        )


def scores_markdown(scores: dict) -> str:
    lines = [
        "# Applicability tag audit scores",
        "",
        f"Reviewed chunks: {scores['reviewed_rows']}",
        "",
        "## G2",
        "",
        "| Attribute | Occurrences | Precision (95% CI) | Recall raw (95% CI) | Recall weighted (95% CI) | Result |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for attribute, metric in scores["per_attribute"].items():
        if not metric["gated"]:
            continue
        passed = (
            metric["precision"] is not None
            and metric["precision"] >= 0.8
            and metric["weighted_recall"] is not None
            and metric["weighted_recall"] >= 0.7
        )
        lines.append(
            f"| {attribute} | {metric['occurrences']} | "
            f"{_format_metric(metric['precision'], metric['precision_ci'])} | "
            f"{_format_metric(metric['recall'], metric['recall_ci'])} | "
            f"{_format_metric(metric['weighted_recall'], metric['weighted_recall_ci'])} | "
            f"{'PASS' if passed else 'FAIL'} |"
        )
    verdict = "PASS" if scores["g2"]["passed"] else "FAIL"
    failures = ", ".join(scores["g2"]["failing_attributes"]) or "none"
    unknown = scores["unknown_chunks"]
    lines.extend(
        [
            "",
            "| Method | Occurrences | Precision (95% CI) | Recall raw (95% CI) | Recall weighted (95% CI) | Result |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for method, metric in scores["method_summary"].items():
        lines.append(
            f"| {method} | {metric['occurrences']} | "
            f"{_format_metric(metric['precision'], metric['precision_ci'])} | "
            f"{_format_metric(metric['recall'], metric['recall_ci'])} | "
            f"{_format_metric(metric['weighted_recall'], metric['weighted_recall_ci'])} | "
            f"{'PASS' if metric['passed'] else 'FAIL'} |"
        )
    not_sampled = ", ".join(scores["not_sampled_buckets"]) or "none"
    lines.extend(
        [
            "",
            f"G2 verdict: **{verdict}**. Failing gated attributes: {failures}.",
            f"Index buckets not sampled: {not_sampled}.",
            f"Unknown (`llm_rejected`) chunks: {unknown['count']}; with any missed value: {unknown['with_any_missed']}.",
            "",
            "## All attributes",
            "",
        ]
    )
    _append_metric_table(lines, scores["per_attribute"], include_gate=True)
    for split_name in ("by_method", "by_bucket", "by_campus"):
        lines.extend(["", f"## {split_name.replace('_', ' ')}", ""])
        for group, attributes in scores[split_name].items():
            lines.extend([f"### {group}", ""])
            _append_metric_table(lines, attributes)
            lines.append("")
    lines.extend(["## Out-of-vocabulary conditions", ""])
    if scores["out_of_vocabulary_conditions"]:
        lines.extend(["| Condition | Reviewed chunks |", "|---|---:|"])
        lines.extend(
            f"| {_markdown_cell(condition)} | {count} |"
            for condition, count in scores["out_of_vocabulary_conditions"].items()
        )
    else:
        lines.append("None recorded.")
    lines.extend(["", "## Audience distribution", "", "| Audience | Reviewed chunks |", "|---|---:|"])
    lines.extend(
        f"| {audience} | {count} |"
        for audience, count in scores["audience_distribution"].items()
    )
    return "\n".join(lines).rstrip() + "\n"


def write_scores(scores: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores.json").write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    (out / "scores.md").write_text(scores_markdown(scores), encoding="utf-8")


def frequency_data(db: Database) -> dict:
    documents = {
        document["doc_id"]: _document_campus(document)
        for document in db.documents.find({}, {"_id": 0})
    }
    counts: dict[tuple[str, str], dict[str, Any]] = {}
    requirements: Counter[str] = Counter()

    def entry(attribute: str, value: str) -> dict[str, Any]:
        return counts.setdefault(
            (attribute, value),
            {"attribute": attribute, "value": value, "count": 0,
             "by_method": {"rule": 0, "llm": 0}, "by_campus": {"seoul": 0, "erica": 0}},
        )

    for attribute in ATTRIBUTES:
        if attribute in VOCABULARY:
            for value in VOCABULARY[attribute]:
                entry(attribute, value)

    chunk_count = 0
    for chunk in db.chunks.find({}, {"_id": 0}):
        chunk_count += 1
        campus = documents.get(chunk.get("doc_id"))
        if campus is None:
            raise AuditError(f"Chunk {chunk.get('chunk_id')} has no document campus")
        condition = chunk.get("applicability") or {}
        methods = condition.get("extraction_method") or {}
        for attribute in ATTRIBUTES:
            for value in _values(condition, attribute):
                item = entry(attribute, value)
                item["count"] += 1
                item["by_method"][_method_family(methods.get(attribute), chunk.get("tag_bucket"))] += 1
                item["by_campus"][campus] += 1
        for phrase in condition.get("requirements") or []:
            normalized = " ".join(str(phrase).split())
            if normalized:
                requirements[normalized] += 1

    attribute_order = {attribute: index for index, attribute in enumerate(ATTRIBUTES)}
    rows = sorted(counts.values(), key=lambda row: (attribute_order[row["attribute"]], row["value"]))
    never_seen = [f"{row['attribute']}={row['value']}" for row in rows if row["attribute"] in VOCABULARY and row["count"] == 0]
    top_requirements = [
        {"phrase": phrase, "count": count}
        for phrase, count in sorted(requirements.items(), key=lambda item: (-item[1], item[0]))[:15]
    ]
    return {"index_id": db.index_id, "chunks": chunk_count, "frequencies": rows,
            "never_seen": never_seen, "top_requirements": top_requirements}


def frequency_markdown(report: dict) -> str:
    lines = [
        f"# Applicability frequency: {report['index_id']}",
        "",
        f"Chunks: {report['chunks']}",
        "",
        "| Attribute | Value | Total | Rule | LLM | Seoul | ERICA |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["frequencies"]:
        lines.append(
            f"| {row['attribute']} | {row['value']} | {row['count']} | {row['by_method']['rule']} | "
            f"{row['by_method']['llm']} | {row['by_campus']['seoul']} | {row['by_campus']['erica']} |"
        )
    lines.extend(["", "## Vocabulary values never seen", ""])
    lines.extend(f"- `{value}`" for value in report["never_seen"])
    if not report["never_seen"]:
        lines.append("None.")
    lines.extend(["", "## Most frequent requirement phrases", "", "| Phrase | Chunks |", "|---|---:|"])
    lines.extend(f"| {row['phrase'].replace('|', '\\|')} | {row['count']} |" for row in report["top_requirements"])
    return "\n".join(lines) + "\n"


def write_frequency(report: dict, path: Path) -> None:
    if path.suffix not in (".md", ".json"):
        raise AuditError("Frequency output must end in .md or .json")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report, indent=2) + "\n" if path.suffix == ".json" else frequency_markdown(report)
    path.write_text(content, encoding="utf-8")


def connect_index(index_id: str) -> Database:
    return Database.connect(get_settings()).for_index(index_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit AAES applicability tags")
    commands = parser.add_subparsers(dest="command", required=True)

    sample = commands.add_parser("sample", help="write the stratified human-review sheet")
    sample.add_argument("--index-id", required=True)
    sample.add_argument("--n", type=int, default=50)
    sample.add_argument("--seed", type=int, default=20261110)
    sample.add_argument("--out", type=Path, default=REPORT_DIR / "notes" / "tag_audit.csv")
    sample.add_argument("--force", action="store_true")

    score = commands.add_parser("score", help="validate and score a completed review sheet")
    score.add_argument("--csv", type=Path, required=True)
    score.add_argument("--out", type=Path, default=RESULTS_DIR / "tag_audit" / INDEX_ID)

    frequency = commands.add_parser("frequency", help="count tags over every indexed chunk")
    frequency.add_argument("--index-id", required=True)
    frequency.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "sample":
            existing = next((path for path in (args.out, sidecar_path(args.out)) if path.exists()), None)
            if existing and not args.force:
                raise AuditError(f"Refusing to overwrite existing audit file: {existing} (use --force)")
            db = connect_index(args.index_id)
            sample = sample_records(audit_records(db, load_snapshot_rows(db)), args.n, args.seed)
            metadata = sample_metadata(
                args.index_id,
                args.seed,
                sample,
                manifest_bucket_partition(db),
            )
            write_sample_csv(sample, args.out, metadata, args.force)
            counts = stratum_counts(sample)
            for name in ("campus_seoul", "campus_erica", *(name for name, _, _ in FLOORS)):
                print(f"{name}: {counts[name]}")
            print(f"Wrote {len(sample)} chunks to {args.out}")
            print(f"Wrote sample metadata to {sidecar_path(args.out)}")
        elif args.command == "score":
            scores = score_csv(args.csv)
            write_scores(scores, args.out)
            print(f"Reviewed rows: {scores['reviewed_rows']}")
            print(f"G2: {'PASS' if scores['g2']['passed'] else 'FAIL'}")
            print(f"Wrote {args.out / 'scores.json'} and {args.out / 'scores.md'}")
        else:
            db = connect_index(args.index_id)
            report = frequency_data(db)
            out = args.out or RESULTS_DIR / "tag_audit" / args.index_id / "frequency.md"
            write_frequency(report, out)
            print(f"Counted {report['chunks']} chunks; wrote {out}")
        return 0
    except SheetValidationError as exc:
        for error in exc.errors:
            print(error, file=sys.stderr)
        return 2
    except (AuditError, FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
