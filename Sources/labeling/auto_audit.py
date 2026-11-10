"""Sample and score the blind automated applicability-tag audit.

Run from ``Sources/``::

    python -m labeling.auto_audit sample --index-id hyu_20261110_97dc1269_r3
    python -m labeling.auto_audit compare --index-id hyu_20261110_97dc1269_r3 --reference <reference.jsonl>
    python -m labeling.auto_audit finalize --index-id hyu_20261110_97dc1269_r3 --reference <reference.jsonl> --decisions <decisions.jsonl>
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from app.config import RESULTS_DIR, get_settings
from app.database import Database
from app.rag.applicability import CONSTRAINT_ATTRIBUTES, SCOPES, TERM_RE, VOCABULARY
from labeling.audit_tags import (
    BUCKETS,
    AuditError,
    _document_campus,
    _method_family,
    bucket_weighted_recall,
    manifest_bucket_partition,
    wilson_interval,
)

ATTRIBUTES = (*CONSTRAINT_ATTRIBUTES, "campus", "scope", "effective_term")
BUCKET_QUOTAS = {
    "rule_tagged": 50,
    "rule_unconditioned": 25,
    "llm_tagged": 20,
    "llm_unconditioned": 35,
}
FLOORS: tuple[tuple[str, int, Callable[[dict], bool]], ...] = (
    ("topik_text", 15, lambda row: re.search(r"\bTOPIK\b", row.get("text", ""), re.IGNORECASE) is not None),
    ("rule_unconditioned", 20, lambda row: row.get("tag_bucket") == "rule_unconditioned"),
    ("any_of", 4, lambda row: bool((row.get("applicability") or {}).get("any_of"))),
)
REFERENCE_FIELDS = {
    "chunk_id", "constraints", "any_of", "scope", "campus", "effective_term", "evidence",
    "topik_scope", "audience", "out_of_vocabulary_condition", "notes",
}
LIMITATION = (
    "**Limitation (state it in every report):** this is an automated audit. The reference annotator, "
    "Codex, also wrote the tagging rules, and the audit is not human-validated."
)


class ReferenceValidationError(AuditError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def output_dir(index_id: str) -> Path:
    return RESULTS_DIR / "tag_audit" / index_id / "auto"


def load_records(db: Database, chunk_ids: list[str] | None = None) -> list[dict]:
    """Join MongoDB chunks to the document fields needed by the blind audit."""
    query = {"chunk_id": {"$in": chunk_ids}} if chunk_ids is not None else {}
    chunks = list(db.chunks.find(query, {"_id": 0}))
    doc_ids = list({chunk.get("doc_id") for chunk in chunks})
    documents = {
        row["doc_id"]: row
        for row in db.documents.find({"doc_id": {"$in": doc_ids}}, {"_id": 0})
    }
    records = []
    for chunk in chunks:
        document = documents.get(chunk.get("doc_id"))
        if document is None:
            raise AuditError(f"Chunk {chunk.get('chunk_id')} has no document")
        metadata = document.get("metadata") or {}
        heading_path = chunk.get("heading_path")
        if heading_path is None:
            heading_path = [chunk["section"]] if chunk.get("section") else []
        records.append(
            {
                **chunk,
                "_campus": _document_campus(document),
                "_title": document.get("title") or "",
                "_post_date": metadata.get("post_date") or None,
                "_heading_path": list(heading_path),
            }
        )
    records.sort(key=lambda row: row["chunk_id"])
    if chunk_ids is not None:
        found = {row["chunk_id"] for row in records}
        missing = [chunk_id for chunk_id in chunk_ids if chunk_id not in found]
        if missing:
            raise AuditError(f"MongoDB is missing sampled chunks: {', '.join(missing)}")
    return records


def _minimum_erica(target: int, records: list[dict]) -> int:
    wanted = math.ceil(target * 0.3)
    available = sum(row["_campus"] == "erica" for row in records)
    return wanted if available >= wanted else available


def _bucket_targets(records: list[dict], n: int, rng: random.Random) -> dict[str, int]:
    by_bucket = {bucket: [row for row in records if row.get("tag_bucket") == bucket] for bucket in BUCKETS}
    invalid = sorted({row.get("tag_bucket") for row in records} - set(BUCKETS), key=str)
    if invalid:
        raise AuditError(f"Index contains unknown tag buckets: {invalid}")
    targets = {
        "rule_tagged": BUCKET_QUOTAS["rule_tagged"],
        "rule_unconditioned": BUCKET_QUOTAS["rule_unconditioned"],
        "llm_tagged": min(BUCKET_QUOTAS["llm_tagged"], len(by_bucket["llm_tagged"])),
        "llm_unconditioned": BUCKET_QUOTAS["llm_unconditioned"],
        "llm_rejected": len(by_bucket["llm_rejected"]),
        "llm_errors": len(by_bucket["llm_errors"]),
    }
    for bucket in ("rule_tagged", "rule_unconditioned", "llm_unconditioned"):
        if len(by_bucket[bucket]) < targets[bucket]:
            raise AuditError(
                f"Cannot meet {bucket} quota: need {targets[bucket]}, index has {len(by_bucket[bucket])}"
            )
    base = sum(targets.values())
    if base > n:
        raise AuditError(f"Bucket quotas require {base} chunks, more than --n {n}")
    fill = [
        bucket
        for bucket in ("rule_tagged", "llm_unconditioned")
        for _ in range(len(by_bucket[bucket]) - targets[bucket])
    ]
    rng.shuffle(fill)
    if len(fill) < n - base:
        raise AuditError(f"Cannot fill sample to {n}: quotas plus eligible chunks provide only {base + len(fill)}")
    for bucket in fill[: n - base]:
        targets[bucket] += 1
    return targets


def _sample_bucket(rows: list[dict], target: int, rng: random.Random) -> list[dict]:
    erica = sorted((row for row in rows if row["_campus"] == "erica"), key=lambda row: row["chunk_id"])
    rng.shuffle(erica)
    chosen = erica[: _minimum_erica(target, rows)]
    chosen_ids = {row["chunk_id"] for row in chosen}
    rest = sorted((row for row in rows if row["chunk_id"] not in chosen_ids), key=lambda row: row["chunk_id"])
    rng.shuffle(rest)
    return chosen + rest[: target - len(chosen)]


def _floor_counts(records: list[dict]) -> dict[str, int]:
    return {name: sum(predicate(row) for row in records) for name, _, predicate in FLOORS}


def _ensure_floors(selected: list[dict], records: list[dict], targets: dict[str, int], rng: random.Random) -> None:
    selected_ids = {row["chunk_id"] for row in selected}
    completed: list[tuple[str, int, Callable[[dict], bool]]] = []
    for name, target, predicate in FLOORS:
        while sum(predicate(row) for row in selected) < target:
            candidates = [row for row in records if row["chunk_id"] not in selected_ids and predicate(row)]
            candidates.sort(key=lambda row: row["chunk_id"])
            rng.shuffle(candidates)
            swapped = False
            for candidate in candidates:
                bucket = candidate["tag_bucket"]
                victims = [row for row in selected if row["tag_bucket"] == bucket and not predicate(row)]
                victims.sort(key=lambda row: row["chunk_id"])
                rng.shuffle(victims)
                for victim in victims:
                    proposed = [row for row in selected if row is not victim] + [candidate]
                    bucket_rows = [row for row in records if row["tag_bucket"] == bucket]
                    bucket_selected = [row for row in proposed if row["tag_bucket"] == bucket]
                    if sum(row["_campus"] == "erica" for row in bucket_selected) < _minimum_erica(targets[bucket], bucket_rows):
                        continue
                    if any(sum(done(row) for row in proposed) < floor for _, floor, done in completed):
                        continue
                    selected.remove(victim)
                    selected.append(candidate)
                    selected_ids.remove(victim["chunk_id"])
                    selected_ids.add(candidate["chunk_id"])
                    swapped = True
                    break
                if swapped:
                    break
            if not swapped:
                achieved = sum(predicate(row) for row in selected)
                raise AuditError(f"Cannot meet {name} floor: need {target}, achieved {achieved}")
        completed.append((name, target, predicate))


def sample_records(records: list[dict], n: int = 150, seed: int = 20261111) -> tuple[list[dict], dict[str, int]]:
    if n <= 0:
        raise AuditError("--n must be positive")
    records = sorted(records, key=lambda row: row["chunk_id"])
    if len({row["chunk_id"] for row in records}) != len(records):
        raise AuditError("Index contains duplicate chunk_id values")
    rng = random.Random(seed)
    targets = _bucket_targets(records, n, rng)
    selected = []
    for bucket in BUCKETS:
        rows = [row for row in records if row.get("tag_bucket") == bucket]
        selected.extend(_sample_bucket(rows, targets[bucket], rng))
    _ensure_floors(selected, records, targets, rng)
    selected.sort(key=lambda row: row["chunk_id"])
    counts = _floor_counts(selected)
    failures = [f"{name}: need {target}, achieved {counts[name]}" for name, target, _ in FLOORS if counts[name] < target]
    if failures:
        raise AuditError("Sampling floors failed: " + "; ".join(failures))
    return selected, targets


def blind_row(record: dict) -> dict:
    return {
        "chunk_id": record["chunk_id"],
        "site": record["_campus"],
        "title": record["_title"],
        "heading_path": record["_heading_path"],
        "post_date": record["_post_date"],
        "text": record.get("text") or "",
    }


def sample_metadata(index_id: str, seed: int, records: list[dict], targets: dict[str, int], partition: dict[str, int]) -> dict:
    by_bucket = Counter(row["tag_bucket"] for row in records)
    by_campus = Counter(row["_campus"] for row in records)
    by_bucket_campus = {
        bucket: dict(Counter(row["_campus"] for row in records if row["tag_bucket"] == bucket))
        for bucket in BUCKETS
    }
    return {
        "index_id": index_id,
        "seed": seed,
        "n": len(records),
        "chunk_ids": [row["chunk_id"] for row in records],
        "chunks": {
            row["chunk_id"]: {"bucket": row["tag_bucket"], "campus": row["_campus"]}
            for row in records
        },
        "bucket_targets": targets,
        "achieved_strata": {
            "by_bucket": {bucket: by_bucket[bucket] for bucket in BUCKETS},
            "by_campus": {campus: by_campus[campus] for campus in VOCABULARY["campus"]},
            "by_bucket_campus": by_bucket_campus,
            "floors": _floor_counts(records),
        },
        "bucket_partition": partition,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_sample(records: list[dict], metadata: dict, out: Path, force: bool = False) -> None:
    blind = out / "blind_inputs.jsonl"
    meta = out / "sample_meta.json"
    existing = next((path for path in (blind, meta) if path.exists()), None)
    if existing and not force:
        raise AuditError(f"Refusing to overwrite existing audit file: {existing} (use --force)")
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(blind, [blind_row(record) for record in records])
    meta.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_sample_metadata(path: Path, index_id: str) -> dict:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"Cannot read sample metadata {path}: {exc}") from exc
    if metadata.get("index_id") != index_id:
        raise AuditError(f"Sample metadata is for {metadata.get('index_id')!r}, not {index_id!r}")
    partition = metadata.get("bucket_partition")
    chunks = metadata.get("chunks")
    ids = metadata.get("chunk_ids")
    if not isinstance(partition, dict) or any(not isinstance(partition.get(bucket), int) for bucket in BUCKETS):
        raise AuditError("Sample metadata has no valid six-bucket partition")
    if not isinstance(chunks, dict) or not isinstance(ids, list) or set(chunks) != set(ids):
        raise AuditError("Sample metadata has invalid chunk strata")
    return metadata


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _read_jsonl(path: Path, label: str) -> tuple[list[dict], list[str]]:
    rows, errors = [], []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise AuditError(f"Cannot read {label} {path}: {exc}") from exc
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {number}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(row, dict):
            errors.append(f"line {number}: expected a JSON object")
            continue
        row["_line"] = number
        rows.append(row)
    return rows, errors


def _valid_attribute_values(attribute: str, values: Any) -> bool:
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        return False
    if attribute == "scope":
        return all(value in SCOPES for value in values)
    if attribute == "effective_term":
        return all(TERM_RE.fullmatch(value) for value in values)
    return attribute in VOCABULARY and all(value in VOCABULARY[attribute] for value in values)


def validate_reference(path: Path, records: list[dict], expected_ids: list[str]) -> list[dict]:
    rows, errors = _read_jsonl(path, "reference")
    text_by_id = {row["chunk_id"]: row.get("text") or "" for row in records}
    seen: set[str] = set()
    valid_rows: list[dict] = []
    for row in rows:
        line = row.pop("_line")
        prefix = f"line {line}"
        missing = sorted(REFERENCE_FIELDS - set(row))
        if missing:
            errors.append(f"{prefix}: missing fields {missing}")
        chunk_id = row.get("chunk_id")
        if not isinstance(chunk_id, str) or chunk_id not in text_by_id:
            errors.append(f"{prefix}: unknown chunk_id {chunk_id!r}")
            continue
        if chunk_id in seen:
            errors.append(f"{prefix}: duplicate chunk_id {chunk_id!r}")
            continue
        seen.add(chunk_id)
        constraints = row.get("constraints")
        if not isinstance(constraints, dict):
            errors.append(f"{prefix} constraints: expected an object")
            constraints = {}
        for attribute, values in constraints.items():
            if attribute not in CONSTRAINT_ATTRIBUTES or not _valid_attribute_values(attribute, values):
                errors.append(f"{prefix} {attribute}: values outside vocabulary v1: {values!r}")
        any_of = row.get("any_of")
        if not isinstance(any_of, list):
            errors.append(f"{prefix} any_of: expected a list")
            any_of = []
        elif len(any_of) == 1:
            errors.append(f"{prefix} any_of: one set belongs in constraints; alternatives need at least two sets")
        for group_index, group in enumerate(any_of):
            if not isinstance(group, dict) or not group:
                errors.append(f"{prefix} any_of[{group_index}]: expected a non-empty object")
                continue
            for attribute, values in group.items():
                if attribute not in CONSTRAINT_ATTRIBUTES or not _valid_attribute_values(attribute, values):
                    errors.append(f"{prefix} any_of[{group_index}].{attribute}: values outside vocabulary v1: {values!r}")
        scope = row.get("scope")
        if scope not in SCOPES:
            errors.append(f"{prefix} scope: {scope!r} is outside {SCOPES}")
        campus = row.get("campus")
        if not _valid_attribute_values("campus", campus) or not campus:
            errors.append(f"{prefix} campus: expected a non-empty v1 value list")
        if scope == "national" and isinstance(campus, list) and set(campus) != set(VOCABULARY["campus"]):
            errors.append(f"{prefix} campus: national scope must include both campuses")
        term = row.get("effective_term")
        if term is not None and (not isinstance(term, str) or not TERM_RE.fullmatch(term)):
            errors.append(f"{prefix} effective_term: expected null or YYYY-1/YYYY-2")
        evidence = row.get("evidence")
        if not isinstance(evidence, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in evidence.items()):
            errors.append(f"{prefix} evidence: expected an object of string quotes")
            evidence = {}
        normalized_text = _normalized(text_by_id[chunk_id])
        for field, quote in evidence.items():
            if not quote or _normalized(quote) not in normalized_text:
                errors.append(f"{prefix} evidence.{field}: quote is not in the chunk text")
        constrained = set(constraints)
        constrained.update(attribute for group in any_of if isinstance(group, dict) for attribute in group)
        for attribute in sorted(constrained):
            if attribute not in evidence and not (attribute in {key for group in any_of if isinstance(group, dict) for key in group} and "any_of" in evidence):
                errors.append(f"{prefix} evidence.{attribute}: every non-campus vocabulary value needs a quote")
        if row.get("topik_scope") not in (None, "whole_chunk", "one_line"):
            errors.append(f"{prefix} topik_scope: expected whole_chunk, one_line or null")
        audience = row.get("audience")
        audiences = audience.split("|") if isinstance(audience, str) else []
        if audience is not None and (not isinstance(audience, str) or any(value not in {"applicant", "admitted", "enrolled"} for value in audiences)):
            errors.append(f"{prefix} audience: expected applicant, admitted, enrolled, a pipe list or null")
        for field in ("out_of_vocabulary_condition", "notes"):
            if not isinstance(row.get(field), str):
                errors.append(f"{prefix} {field}: expected a string")
        valid_rows.append(row)
    missing_ids = [chunk_id for chunk_id in expected_ids if chunk_id not in seen]
    extra_ids = sorted(seen - set(expected_ids))
    if missing_ids:
        errors.append(f"reference: missing sampled chunk_ids {missing_ids}")
    if extra_ids:
        errors.append(f"reference: unexpected chunk_ids {extra_ids}")
    if errors:
        raise ReferenceValidationError(errors)
    order = {chunk_id: index for index, chunk_id in enumerate(expected_ids)}
    return sorted(valid_rows, key=lambda row: order[row["chunk_id"]])


def _values(condition: dict, attribute: str) -> set[str]:
    if attribute == "campus":
        return set(condition.get("campus") or [])
    if attribute == "scope":
        return {condition["scope"]} if condition.get("scope") else set()
    if attribute == "effective_term":
        return {condition["effective_term"]} if condition.get("effective_term") else set()
    values = set((condition.get("constraints") or {}).get(attribute) or [])
    for group in condition.get("any_of") or []:
        values.update(group.get(attribute) or [])
    return values


def _evidence(condition: dict, attribute: str) -> str | None:
    evidence = condition.get("evidence") or {}
    if isinstance(evidence.get(attribute), str):
        return evidence[attribute]
    if any(attribute in group for group in condition.get("any_of") or []) and isinstance(evidence.get("any_of"), str):
        return evidence["any_of"]
    return None


def _canonical_any_of(condition: dict) -> tuple:
    return tuple(
        sorted(
            tuple(sorted((attribute, tuple(sorted(values))) for attribute, values in group.items()))
            for group in condition.get("any_of") or []
        )
    )


def _empty_counts() -> dict[str, dict[str, Any]]:
    return {attribute: {"tp": 0, "fp": 0, "fn": 0, "rows": set()} for attribute in ATTRIBUTES}


def _add(counts: dict, attribute: str, chunk_id: str, tp: int, fp: int, fn: int) -> None:
    entry = counts[attribute]
    entry["tp"] += tp
    entry["fp"] += fp
    entry["fn"] += fn
    if tp or fp or fn:
        entry["rows"].add(chunk_id)


def _metric(entry: dict, bucket_entries: dict[str, dict], partition: dict[str, int], sampled: dict[str, int]) -> dict:
    tp, fp, fn = entry["tp"], entry["fp"], entry["fn"]
    precision_n, recall_n = tp + fp, tp + fn
    weighted = bucket_weighted_recall(bucket_entries, partition, sampled)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / precision_n if precision_n else None,
        "precision_ci": wilson_interval(tp, precision_n),
        "recall": tp / recall_n if recall_n else None,
        "recall_ci": wilson_interval(tp, recall_n),
        "weighted_recall": weighted,
        # Same approximation used by audit_tags; bootstrap if a gate result is borderline.
        "weighted_recall_ci": wilson_interval(weighted * recall_n, recall_n) if weighted is not None else None,
        "occurrences": len(entry["rows"]),
        "gated": len(entry["rows"]) >= 5,
    }


def _metrics(counts: dict, counts_by_bucket: dict[str, dict], partition: dict[str, int], sampled: dict[str, int]) -> dict:
    return {
        attribute: _metric(
            entry,
            {bucket: bucket_counts[attribute] for bucket, bucket_counts in counts_by_bucket.items()},
            partition,
            sampled,
        )
        for attribute, entry in counts.items()
    }


def score_comparison(
    records: list[dict],
    references: list[dict],
    metadata: dict,
    overrides: dict[tuple[str, str], set[str]] | None = None,
    excluded: set[tuple[str, str]] | None = None,
) -> dict:
    """Compare values. Example: TP=4, FP=2, FN=3 gives P=4/6 and R=4/7.

    A four-chunk test covers an ``any_of`` value and both method families. Predicted
    TP/FP use the field's extraction method; an FN uses its chunk bucket family.
    """
    overrides, excluded = overrides or {}, excluded or set()
    reference_by_id = {row["chunk_id"]: row for row in references}
    overall = _empty_counts()
    by_method = {family: _empty_counts() for family in ("rule", "llm")}
    by_bucket = {bucket: _empty_counts() for bucket in BUCKETS}
    by_campus = {campus: _empty_counts() for campus in VOCABULARY["campus"]}
    by_method_bucket = {family: {bucket: _empty_counts() for bucket in BUCKETS} for family in ("rule", "llm")}
    by_campus_bucket = {campus: {bucket: _empty_counts() for bucket in BUCKETS} for campus in VOCABULARY["campus"]}
    sampled = Counter(item["bucket"] for item in metadata["chunks"].values())
    any_of_all = any_of_all_correct = any_of_present = any_of_present_correct = 0

    for record in records:
        chunk_id = record["chunk_id"]
        predicted = record.get("applicability") or {}
        reference = reference_by_id[chunk_id]
        bucket, campus = record["tag_bucket"], record["_campus"]
        pred_any, ref_any = _canonical_any_of(predicted), _canonical_any_of(reference)
        any_of_all += 1
        any_of_all_correct += pred_any == ref_any
        if pred_any or ref_any:
            any_of_present += 1
            any_of_present_correct += pred_any == ref_any
        methods = predicted.get("extraction_method") or {}
        for attribute in ATTRIBUTES:
            key = (chunk_id, attribute)
            if key in excluded:
                continue
            pred = _values(predicted, attribute)
            ref = overrides.get(key, _values(reference, attribute))
            tp, fp, fn = len(pred & ref), len(pred - ref), len(ref - pred)
            _add(overall, attribute, chunk_id, tp, fp, fn)
            _add(by_bucket[bucket], attribute, chunk_id, tp, fp, fn)
            _add(by_campus[campus], attribute, chunk_id, tp, fp, fn)
            _add(by_campus_bucket[campus][bucket], attribute, chunk_id, tp, fp, fn)
            if tp or fp:
                method = methods.get("any_of") if any(attribute in group for group in predicted.get("any_of") or []) else methods.get(attribute)
                family = _method_family(method, bucket)
                _add(by_method[family], attribute, chunk_id, tp, fp, 0)
                _add(by_method_bucket[family][bucket], attribute, chunk_id, tp, fp, 0)
            if fn:
                family = _method_family(None, bucket)
                _add(by_method[family], attribute, chunk_id, 0, 0, fn)
                _add(by_method_bucket[family][bucket], attribute, chunk_id, 0, 0, fn)

    partition = metadata["bucket_partition"]
    per_attribute = _metrics(overall, by_bucket, partition, sampled)
    failing = [
        attribute for attribute, metric in per_attribute.items()
        if metric["gated"] and (
            metric["precision"] is None or metric["precision"] < 0.8
            or metric["weighted_recall"] is None or metric["weighted_recall"] < 0.7
        )
    ]
    return {
        "index_id": metadata["index_id"],
        "sample_n": len(records),
        "per_attribute": per_attribute,
        "by_method": {
            family: _metrics(counts, by_method_bucket[family], partition, sampled)
            for family, counts in by_method.items()
        },
        "by_bucket": {
            bucket: _metrics(counts, {bucket: counts}, partition, sampled)
            for bucket, counts in by_bucket.items()
        },
        "by_campus": {
            campus: _metrics(counts, by_campus_bucket[campus], partition, sampled)
            for campus, counts in by_campus.items()
        },
        "any_of_exact_match": {
            "all_chunks": {"matches": any_of_all_correct, "n": any_of_all, "rate": any_of_all_correct / any_of_all if any_of_all else None},
            "chunks_with_any_of": {"matches": any_of_present_correct, "n": any_of_present, "rate": any_of_present_correct / any_of_present if any_of_present else None},
        },
        "g2": {"passed": not failing, "failing_attributes": failing},
    }


def disagreement_rows(records: list[dict], references: list[dict], seed: int) -> tuple[list[dict], dict]:
    reference_by_id = {row["chunk_id"]: row for row in references}
    rows, keys = [], []
    for record in records:
        predicted = record.get("applicability") or {}
        reference = reference_by_id[record["chunk_id"]]
        for attribute in ATTRIBUTES:
            pred_values, ref_values = sorted(_values(predicted, attribute)), sorted(_values(reference, attribute))
            if pred_values == ref_values:
                continue
            predicted_first = random.Random(f"{seed}:{record['chunk_id']}:{attribute}").randrange(2) == 0
            sides = [
                (pred_values, _evidence(predicted, attribute), "predicted"),
                (ref_values, _evidence(reference, attribute), "reference"),
            ]
            if not predicted_first:
                sides.reverse()
            rows.append(
                {
                    "chunk_id": record["chunk_id"],
                    "text": record.get("text") or "",
                    "heading_path": record["_heading_path"],
                    "attribute": attribute,
                    "value_a": sides[0][0],
                    "value_b": sides[1][0],
                    "evidence_a": sides[0][1],
                    "evidence_b": sides[1][1],
                }
            )
            keys.append(
                {
                    "chunk_id": record["chunk_id"],
                    "attribute": attribute,
                    "predicted_side": "a" if sides[0][2] == "predicted" else "b",
                    "reference_side": "a" if sides[0][2] == "reference" else "b",
                }
            )
    return rows, {"seed": seed, "rows": keys}


def _format_metric(value: float | None, interval: list[float] | None) -> str:
    if value is None or interval is None:
        return "null [null]"
    return f"{value:.3f} [{interval[0]:.3f}, {interval[1]:.3f}]"


def _append_table(lines: list[str], metrics: dict, gate: bool = False) -> None:
    if gate:
        lines.extend(
            [
                "| Attribute | Occurrences | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) | Result |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for attribute, metric in metrics.items():
            if not metric["gated"]:
                continue
            passed = (
                metric["precision"] is not None and metric["precision"] >= 0.8
                and metric["weighted_recall"] is not None and metric["weighted_recall"] >= 0.7
            )
            lines.append(
                f"| {attribute} | {metric['occurrences']} | "
                f"{_format_metric(metric['precision'], metric['precision_ci'])} | "
                f"{_format_metric(metric['recall'], metric['recall_ci'])} | "
                f"{_format_metric(metric['weighted_recall'], metric['weighted_recall_ci'])} | "
                f"{'PASS' if passed else 'FAIL'} |"
            )
        return
    lines.extend(
        [
            "| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for attribute, metric in metrics.items():
        lines.append(
            f"| {attribute} | {metric['occurrences']} | {metric['tp']} | {metric['fp']} | {metric['fn']} | "
            f"{_format_metric(metric['precision'], metric['precision_ci'])} | "
            f"{_format_metric(metric['recall'], metric['recall_ci'])} | "
            f"{_format_metric(metric['weighted_recall'], metric['weighted_recall_ci'])} |"
        )


def scores_markdown(scores: dict, final: bool = False) -> str:
    lines = [LIMITATION, "", "# Automated applicability tag audit", "", "## G2", ""]
    _append_table(lines, scores["per_attribute"], gate=True)
    lines.extend(["", f"G2 verdict: **{'PASS' if scores['g2']['passed'] else 'FAIL'}**."])
    for split in ("by_method", "by_bucket", "by_campus"):
        lines.extend(["", f"## {split.replace('_', ' ')}", ""])
        for name, metrics in scores[split].items():
            lines.extend([f"### {name}", ""])
            _append_table(lines, metrics)
            lines.append("")
    exact = scores["any_of_exact_match"]
    lines.extend(
        [
            "## `any_of` exact match",
            "",
            f"All chunks: {exact['all_chunks']['matches']}/{exact['all_chunks']['n']} ({exact['all_chunks']['rate']}).",
            f"Chunks with `any_of` on either side: {exact['chunks_with_any_of']['matches']}/{exact['chunks_with_any_of']['n']} ({exact['chunks_with_any_of']['rate']}).",
        ]
    )
    if final:
        review = scores["disagreement_review"]
        lines.extend(
            [
                "",
                "## Disagreement review",
                "",
                f"Predicted side: {review['predicted']}; reference side: {review['reference']}; "
                f"both wrong: {review['both_wrong']}; ambiguous: {review['ambiguous']}.",
                "",
                "## Out-of-vocabulary conditions",
                "",
            ]
        )
        oov = scores["out_of_vocabulary_conditions"]
        if oov:
            lines.extend(["| Text | Count |", "|---|---:|"])
            lines.extend(f"| {text.replace('|', '\\|')} | {count} |" for text, count in oov.items())
        else:
            lines.append("None recorded.")
        for label, field in (("Audience", "audience_counts"), ("TOPIK scope", "topik_scope_counts")):
            lines.extend(["", f"## {label}", "", "| Value | Count |", "|---|---:|"])
            lines.extend(f"| {value} | {count} |" for value, count in scores[field].items())
    return "\n".join(lines).rstrip() + "\n"


def write_comparison(out: Path, scores: dict, disagreements: list[dict], key: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "disagreements.jsonl", disagreements)
    (out / "disagreements_key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    (out / "scores_raw.json").write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    (out / "scores_raw.md").write_text(scores_markdown(scores), encoding="utf-8")


def compare(db: Database, index_id: str, reference_path: Path, out: Path) -> dict:
    metadata = read_sample_metadata(out / "sample_meta.json", index_id)
    records = load_records(db, metadata["chunk_ids"])
    references = validate_reference(reference_path, records, metadata["chunk_ids"])
    scores = score_comparison(records, references, metadata)
    disagreements, key = disagreement_rows(records, references, metadata["seed"])
    write_comparison(out, scores, disagreements, key)
    return scores


def _decision_values(attribute: str, values: Any, prefix: str, errors: list[str]) -> set[str]:
    if not _valid_attribute_values(attribute, values):
        errors.append(f"{prefix} correct_values: invalid values for {attribute}: {values!r}")
        return set()
    return set(values)


def read_decisions(path: Path, disagreements: list[dict], key: dict) -> tuple[dict, set, dict, list[dict]]:
    rows, errors = _read_jsonl(path, "decisions")
    disagreements_by_key = {(row["chunk_id"], row["attribute"]): row for row in disagreements}
    key_by_pair = {(row["chunk_id"], row["attribute"]): row for row in key.get("rows", [])}
    overrides: dict[tuple[str, str], set[str]] = {}
    excluded: set[tuple[str, str]] = set()
    summary = Counter({"predicted": 0, "reference": 0, "both_wrong": 0, "ambiguous": 0})
    ambiguous = []
    seen = set()
    for row in rows:
        line = row.pop("_line")
        prefix = f"line {line}"
        pair = (row.get("chunk_id"), row.get("attribute"))
        if pair not in disagreements_by_key or pair not in key_by_pair:
            errors.append(f"{prefix}: no matching disagreement for {pair}")
            continue
        if pair in seen:
            errors.append(f"{prefix}: duplicate decision for {pair}")
            continue
        seen.add(pair)
        decision = row.get("decision")
        reason = row.get("reason")
        if decision not in {"a", "b", "both_wrong", "ambiguous"}:
            errors.append(f"{prefix}: decision must be a, b, both_wrong or ambiguous")
            continue
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix}: reason must be a non-empty string")
        disagreement = disagreements_by_key[pair]
        side_key = key_by_pair[pair]
        if decision in {"a", "b"}:
            overrides[pair] = set(disagreement[f"value_{decision}"])
            winner = "predicted" if side_key["predicted_side"] == decision else "reference"
            summary[winner] += 1
        elif decision == "both_wrong":
            if "correct_values" not in row:
                errors.append(f"{prefix}: both_wrong needs correct_values")
            else:
                overrides[pair] = _decision_values(pair[1], row["correct_values"], prefix, errors)
            summary["both_wrong"] += 1
        else:
            excluded.add(pair)
            summary["ambiguous"] += 1
            ambiguous.append({"chunk_id": pair[0], "attribute": pair[1], "reason": reason})
    missing = sorted(set(disagreements_by_key) - seen)
    if missing:
        errors.append(f"decisions: missing disagreement rows {missing}")
    if errors:
        raise ReferenceValidationError(errors)
    return overrides, excluded, dict(summary), ambiguous


def _reference_counts(references: list[dict]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    oov: Counter[str] = Counter()
    audience = Counter({value: 0 for value in ("applicant", "admitted", "enrolled")})
    topik = Counter({value: 0 for value in ("whole_chunk", "one_line", "null")})
    for row in references:
        text = row.get("out_of_vocabulary_condition", "").strip()
        if text:
            oov[text] += 1
        if row.get("audience"):
            audience.update(row["audience"].split("|"))
        topik[str(row.get("topik_scope") or "null")] += 1
    ordered_oov = dict(sorted(oov.items(), key=lambda item: (-item[1], item[0]))[:15])
    return ordered_oov, dict(audience), dict(topik)


def finalize(db: Database, index_id: str, reference_path: Path, decisions_path: Path, out: Path) -> dict:
    metadata = read_sample_metadata(out / "sample_meta.json", index_id)
    records = load_records(db, metadata["chunk_ids"])
    references = validate_reference(reference_path, records, metadata["chunk_ids"])
    disagreements, _ = _read_jsonl(out / "disagreements.jsonl", "disagreements")
    for row in disagreements:
        row.pop("_line", None)
    try:
        key = json.loads((out / "disagreements_key.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"Cannot read disagreement key: {exc}") from exc
    overrides, excluded, summary, ambiguous = read_decisions(decisions_path, disagreements, key)
    scores = score_comparison(records, references, metadata, overrides, excluded)
    oov, audience, topik = _reference_counts(references)
    scores.update(
        disagreement_review=summary,
        ambiguous_rows=ambiguous,
        out_of_vocabulary_conditions=oov,
        audience_counts=audience,
        topik_scope_counts=topik,
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores_final.json").write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    (out / "scores_final.md").write_text(scores_markdown(scores, final=True), encoding="utf-8")
    return scores


def connect_index(index_id: str) -> Database:
    return Database.connect(get_settings()).for_index(index_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the blind automated AAES tag audit")
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample", help="write the stratified blind sample")
    sample.add_argument("--index-id", required=True)
    sample.add_argument("--n", type=int, default=150)
    sample.add_argument("--seed", type=int, default=20261111)
    sample.add_argument("--force", action="store_true")
    compare_parser = commands.add_parser("compare", help="validate and compare a blind reference")
    compare_parser.add_argument("--index-id", required=True)
    compare_parser.add_argument("--reference", type=Path, required=True)
    finalize_parser = commands.add_parser("finalize", help="apply blind disagreement decisions and re-score")
    finalize_parser.add_argument("--index-id", required=True)
    finalize_parser.add_argument("--reference", type=Path, required=True)
    finalize_parser.add_argument("--decisions", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = output_dir(args.index_id)
    try:
        db = connect_index(args.index_id)
        if args.command == "sample":
            records, targets = sample_records(load_records(db), args.n, args.seed)
            metadata = sample_metadata(args.index_id, args.seed, records, targets, manifest_bucket_partition(db))
            write_sample(records, metadata, out, args.force)
            print(json.dumps(metadata["achieved_strata"], indent=2))
            print(f"Wrote {len(records)} blind chunks to {out}")
        elif args.command == "compare":
            scores = compare(db, args.index_id, args.reference, out)
            print(f"G2 raw: {'PASS' if scores['g2']['passed'] else 'FAIL'}")
            print(f"Wrote raw scores and disagreements to {out}")
        else:
            scores = finalize(db, args.index_id, args.reference, args.decisions, out)
            print(f"G2 final: {'PASS' if scores['g2']['passed'] else 'FAIL'}")
            print(f"Wrote final scores to {out}")
        return 0
    except ReferenceValidationError as exc:
        for error in exc.errors:
            print(error, file=sys.stderr)
        return 2
    except (AuditError, FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
