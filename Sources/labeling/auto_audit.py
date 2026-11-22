"""Sample and score the blind automated applicability-tag audit.

Run from ``Sources/``::

    python -m labeling.auto_audit sample --index-id hyu_20261110_97dc1269_r5 --out test-100
    python -m labeling.auto_audit compare --index-id hyu_20261110_97dc1269_r5 --out test-100 --reference <reference.jsonl>
    python -m labeling.auto_audit finalize --index-id hyu_20261110_97dc1269_r5 --out test-100 --reference <reference.jsonl> --decisions <decisions.jsonl>
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
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
ALWAYS_RESOLVED = {"campus", "scope", "effective_term"}
UNKNOWN_BUCKETS = {"rule_cue_unknown", "llm_rejected", "llm_errors"}
BUCKET_QUOTAS = {
    "rule_tagged": 50,
    "rule_unconditioned": 25,
    "rule_cue_unknown": 35,
    "llm_tagged": 20,
    "llm_unconditioned": 35,
}
FLOORS: tuple[tuple[str, int, Callable[[dict], bool]], ...] = (
    ("topik_text", 15, lambda row: re.search(r"\bTOPIK\b", row.get("text", ""), re.IGNORECASE) is not None),
    ("rule_unconditioned", 20, lambda row: row.get("tag_bucket") == "rule_unconditioned"),
    ("any_of", 4, lambda row: bool((row.get("applicability") or {}).get("any_of"))),
)
CUES = ("visa", "student_type", "degree")
CUE_PATTERNS = {
    "visa": re.compile(r"\b(?:D\s*-\s*\d|F-\d|visa)\b", re.IGNORECASE),
    "student_type": re.compile(
        r"\b(?:exchange|visiting|degree program|language (?:program|training|school)|non-degree)\b",
        re.IGNORECASE,
    ),
    "degree": re.compile(r"\b(?:bachelor|undergraduate|master|doctoral|Ph\.?D\.?|graduate)\b", re.IGNORECASE),
}
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


def output_dir(index_id: str, name: str = "auto") -> Path:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise AuditError("--out must be one folder name")
    return RESULTS_DIR / "tag_audit" / index_id / name


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
    if chunk_ids is not None:
        found = {row["chunk_id"] for row in records}
        missing = [chunk_id for chunk_id in chunk_ids if chunk_id not in found]
        if missing:
            raise AuditError(f"MongoDB is missing sampled chunks: {', '.join(missing)}")
        by_id = {row["chunk_id"]: row for row in records}
        return [by_id[chunk_id] for chunk_id in chunk_ids]
    return sorted(records, key=lambda row: row["chunk_id"])


def _minimum_erica(target: int, records: list[dict]) -> int:
    wanted = math.ceil(target * 0.3)
    available = sum(row["_campus"] == "erica" for row in records)
    return wanted if available >= wanted else available


def _scaled(target: int, n: int) -> int:
    return round(target * n / 150)


def _bucket_targets(
    records: list[dict],
    n: int,
    rng: random.Random,
    quotas: dict[str, int] | None = None,
) -> dict[str, int]:
    quotas = quotas or {}
    invalid_quotas = sorted(set(quotas) - set(BUCKETS))
    if invalid_quotas or any(not isinstance(count, int) or count < 0 for count in quotas.values()):
        raise AuditError(f"Invalid bucket quotas: {quotas}")
    by_bucket = {bucket: [row for row in records if row.get("tag_bucket") == bucket] for bucket in BUCKETS}
    invalid = sorted({row.get("tag_bucket") for row in records} - set(BUCKETS), key=str)
    if invalid:
        raise AuditError(f"Index contains unknown tag buckets: {invalid}")
    targets = {}
    for bucket, rows in by_bucket.items():
        if bucket in quotas:
            targets[bucket] = quotas[bucket]
        elif not rows:
            targets[bucket] = 0
        elif bucket in {"llm_rejected", "llm_errors"}:
            targets[bucket] = len(rows)
        else:
            quota = _scaled(BUCKET_QUOTAS[bucket], n)
            targets[bucket] = min(quota, len(rows)) if bucket == "llm_tagged" else quota
    for bucket in BUCKETS:
        if len(by_bucket[bucket]) < targets[bucket]:
            raise AuditError(
                f"Cannot meet {bucket} quota: need {targets[bucket]}, index has {len(by_bucket[bucket])}"
            )
    base = sum(targets.values())
    if base > n:
        raise AuditError(f"Bucket quotas require {base} chunks, more than --n {n}")
    fill = [
        bucket
        for bucket in ("rule_tagged", "rule_cue_unknown", "llm_unconditioned")
        if bucket not in quotas
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


def _floor_targets(records: list[dict], n: int) -> list[tuple[str, int, int, Callable[[dict], bool]]]:
    targets = []
    for name, base, predicate in FLOORS:
        requested = _scaled(base, n)
        available = sum(predicate(row) for row in records)
        targets.append((name, requested, min(requested, available), predicate))
    return targets


def _floor_report(selected: list[dict], records: list[dict], n: int) -> dict[str, dict[str, int]]:
    return {
        name: {
            "requested": requested,
            "available": sum(predicate(row) for row in records),
            "required": required,
            "achieved": sum(predicate(row) for row in selected),
        }
        for name, requested, required, predicate in _floor_targets(records, n)
    }


def _ensure_floors(selected: list[dict], records: list[dict], targets: dict[str, int], rng: random.Random) -> None:
    selected_ids = {row["chunk_id"] for row in selected}
    completed: list[tuple[str, int, Callable[[dict], bool]]] = []
    for name, requested, target, predicate in _floor_targets(records, len(selected)):
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
                raise AuditError(
                    f"Cannot meet {name} floor: requested {requested}, need {target}, achieved {achieved}"
                )
        completed.append((name, target, predicate))


def sample_records(
    records: list[dict],
    n: int = 150,
    seed: int = 20261111,
    quotas: dict[str, int] | None = None,
) -> tuple[list[dict], dict[str, int]]:
    if n <= 0:
        raise AuditError("--n must be positive")
    records = sorted(records, key=lambda row: row["chunk_id"])
    if len({row["chunk_id"] for row in records}) != len(records):
        raise AuditError("Index contains duplicate chunk_id values")
    rng = random.Random(seed)
    targets = _bucket_targets(records, n, rng, quotas)
    selected = []
    for bucket in BUCKETS:
        rows = [row for row in records if row.get("tag_bucket") == bucket]
        selected.extend(_sample_bucket(rows, targets[bucket], rng))
    _ensure_floors(selected, records, targets, rng)
    selected.sort(key=lambda row: row["chunk_id"])
    report = _floor_report(selected, records, n)
    failures = [
        f"{name}: requested {values['requested']}, need {values['required']}, achieved {values['achieved']}"
        for name, values in report.items()
        if values["achieved"] < values["required"]
    ]
    if failures:
        raise AuditError("Sampling floors failed: " + "; ".join(failures))
    return selected, targets


def cue_name(record: dict) -> str:
    context = "\n".join(
        [record.get("text") or "", record.get("_title") or "", *(record.get("_heading_path") or [])]
    )
    return next((cue for cue in CUES if CUE_PATTERNS[cue].search(context)), "none")


def cue_stratum(record: dict) -> str:
    return f"{record['tag_bucket']}:{cue_name(record)}"


def _proportional_allocation(capacities: dict[str, int], total: int) -> dict[str, int]:
    available = sum(capacities.values())
    if total < 0 or total > available:
        raise AuditError(f"Cannot allocate {total} chunks from {available} available")
    allocation = {key: 0 for key in capacities}
    if total == 0:
        return allocation
    remainders = {}
    for key, capacity in capacities.items():
        allocation[key], remainders[key] = divmod(total * capacity, available)
    left = total - sum(allocation.values())
    for key in sorted(capacities, key=lambda item: (-remainders[item], item)):
        if left == 0:
            break
        if allocation[key] < capacities[key]:
            allocation[key] += 1
            left -= 1
    return allocation


def sample_cue_records(
    records: list[dict],
    n: int,
    seed: int,
    minimums: dict[str, int],
) -> tuple[list[dict], dict]:
    """Sample bucket-by-cue strata and return their design metadata."""
    if n <= 0:
        raise AuditError("--n must be positive")
    if set(minimums) - set(CUES) or any(not isinstance(value, int) or value < 0 for value in minimums.values()):
        raise AuditError(f"Invalid cue minimums: {minimums}")
    if sum(minimums.values()) > n:
        raise AuditError(f"Cue minimums require {sum(minimums.values())} chunks, more than --n {n}")
    records = sorted(records, key=lambda row: row["chunk_id"])
    if len({row["chunk_id"] for row in records}) != len(records):
        raise AuditError("Index contains duplicate chunk_id values")
    invalid = sorted({row.get("tag_bucket") for row in records} - set(BUCKETS), key=str)
    if invalid:
        raise AuditError(f"Index contains unknown tag buckets: {invalid}")
    if n > len(records):
        raise AuditError(f"Cannot sample {n} chunks from {len(records)} available")

    by_stratum: dict[str, list[dict]] = {}
    for record in records:
        by_stratum.setdefault(cue_stratum(record), []).append(record)
    remaining = {key: len(rows) for key, rows in by_stratum.items()}
    targets = {key: 0 for key in by_stratum}
    for cue in CUES:
        requested = minimums.get(cue, 0)
        cue_capacities = {key: count for key, count in remaining.items() if key.endswith(f":{cue}")}
        available = sum(cue_capacities.values())
        if requested > available:
            raise AuditError(f"Cannot meet {cue} cue minimum: need {requested}, available {available}")
        for key, count in _proportional_allocation(cue_capacities, requested).items():
            targets[key] += count
            remaining[key] -= count
    for key, count in _proportional_allocation(remaining, n - sum(targets.values())).items():
        targets[key] += count

    rng = random.Random(seed)
    selected = []
    for key in sorted(by_stratum):
        selected.extend(_sample_bucket(by_stratum[key], targets[key], rng))
    selected.sort(key=lambda row: row["chunk_id"])
    achieved = Counter(cue_name(row) for row in selected)
    failures = [cue for cue, target in minimums.items() if achieved[cue] < target]
    if failures:
        raise AuditError(f"Cue sampling minimums failed: {', '.join(failures)}")
    design = {
        "name": "cue",
        "minimums": {cue: minimums.get(cue, 0) for cue in CUES},
        "strata": {
            key: {
                "bucket": rows[0]["tag_bucket"],
                "cue": cue_name(rows[0]),
                "N_h": len(rows),
                "n_h": targets[key],
            }
            for key, rows in sorted(by_stratum.items())
        },
    }
    return selected, design


def blind_row(record: dict) -> dict:
    return {
        "chunk_id": record["chunk_id"],
        "site": record["_campus"],
        "title": record["_title"],
        "heading_path": record["_heading_path"],
        "post_date": record["_post_date"],
        "text": record.get("text") or "",
    }


def sample_metadata(
    index_id: str,
    seed: int,
    records: list[dict],
    targets: dict[str, int],
    partition: dict[str, int],
    *,
    available_records: list[dict] | None = None,
    excluded_files: list[dict] | None = None,
    reused_from: Path | None = None,
    design: dict | None = None,
) -> dict:
    by_bucket = Counter(row["tag_bucket"] for row in records)
    by_campus = Counter(row["_campus"] for row in records)
    by_cue = Counter(cue_name(row) for row in records) if design else Counter()
    by_bucket_campus = {
        bucket: dict(Counter(row["_campus"] for row in records if row["tag_bucket"] == bucket))
        for bucket in BUCKETS
    }
    metadata = {
        "index_id": index_id,
        "seed": seed,
        "n": len(records),
        "chunk_ids": [row["chunk_id"] for row in records],
        "chunks": {
            row["chunk_id"]: {
                "bucket": row["tag_bucket"],
                "campus": row["_campus"],
                **({"stratum": cue_stratum(row)} if design else {}),
            }
            for row in records
        },
        "bucket_targets": targets,
        "achieved_strata": {
            "by_bucket": {bucket: by_bucket[bucket] for bucket in BUCKETS},
            "by_campus": {campus: by_campus[campus] for campus in VOCABULARY["campus"]},
            "by_bucket_campus": by_bucket_campus,
            **(
                {
                    "by_cue": {
                        cue: by_cue[cue]
                        for cue in (*CUES, "none")
                    }
                }
                if design
                else {}
            ),
            "floors": _floor_report(
                records,
                available_records if available_records is not None else records,
                len(records),
            ),
        },
        "bucket_partition": partition,
        "excluded_files": excluded_files or [],
    }
    if reused_from is not None:
        metadata["reused_from"] = str(reused_from)
    if design is not None:
        metadata["design"] = design
    return metadata


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


def sample_chunk_ids(path: Path) -> tuple[dict, list[str]]:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"Cannot read sample metadata {path}: {exc}") from exc
    chunk_ids = metadata.get("chunk_ids")
    if (
        not isinstance(chunk_ids, list)
        or any(not isinstance(chunk_id, str) or not chunk_id for chunk_id in chunk_ids)
        or len(set(chunk_ids)) != len(chunk_ids)
    ):
        raise AuditError(f"Sample metadata {path} has invalid chunk_ids")
    return metadata, chunk_ids


def write_reused_sample(
    records: list[dict], metadata: dict, source_meta: Path, out: Path, force: bool = False
) -> None:
    source_blind = source_meta.parent / "blind_inputs.jsonl"
    blind_rows, errors = _read_jsonl(source_blind, "blind inputs")
    if errors:
        raise ReferenceValidationError(errors)
    for row in blind_rows:
        row.pop("_line", None)
    expected_ids = metadata["chunk_ids"]
    blind_ids = [row.get("chunk_id") for row in blind_rows]
    if blind_ids != expected_ids:
        raise AuditError(f"Blind inputs {source_blind} do not match the reused chunk_ids")
    by_id = {row["chunk_id"]: row for row in blind_rows}
    for record in records:
        if by_id[record["chunk_id"]].get("text") != (record.get("text") or ""):
            raise AuditError(f"Chunk {record['chunk_id']} text changed since {source_blind}")

    blind = out / "blind_inputs.jsonl"
    meta = out / "sample_meta.json"
    existing = next((path for path in (blind, meta) if path.exists()), None)
    if existing and not force:
        raise AuditError(f"Refusing to overwrite existing audit file: {existing} (use --force)")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_blind, blind)
    meta.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_sample_metadata(path: Path, index_id: str) -> dict:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"Cannot read sample metadata {path}: {exc}") from exc
    if metadata.get("index_id") != index_id:
        raise AuditError(f"Sample metadata is for {metadata.get('index_id')!r}, not {index_id!r}")
    partition = metadata.get("bucket_partition")
    if isinstance(partition, dict):
        partition = {"rule_cue_unknown": 0, **partition}
        metadata["bucket_partition"] = partition
    chunks = metadata.get("chunks")
    ids = metadata.get("chunk_ids")
    if not isinstance(partition, dict) or any(not isinstance(partition.get(bucket), int) for bucket in BUCKETS):
        raise AuditError("Sample metadata has no valid bucket partition")
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
    # rule 1: the title and heading path count as chunk text for evidence (rule 8 tags whole admission guides)
    context_by_id = {row["chunk_id"]: "\n".join([row.get("_title") or "", *(row.get("_heading_path") or []), row.get("text") or ""]) for row in records}
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
        normalized_text = _normalized(context_by_id[chunk_id])
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
    return {
        attribute: {
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "strict_tp": 0,
            "strict_fn": 0,
            "weighted_tp": 0.0,
            "weighted_fp": 0.0,
            "weighted_fn": 0.0,
            "weighted_strict_tp": 0.0,
            "weighted_strict_fn": 0.0,
            "precision_weight_squares": 0.0,
            "recall_weight_squares": 0.0,
            "strict_recall_weight_squares": 0.0,
            "rows": set(),
            "reference_rows": set(),
            "resolved_reference_rows": set(),
            "reference_weights": {},
            "resolved_reference_weights": {},
        }
        for attribute in ATTRIBUTES
    }


def _add(
    counts: dict,
    attribute: str,
    chunk_id: str,
    tp: int,
    fp: int,
    fn: int,
    *,
    strict_tp: int | None = None,
    strict_fn: int | None = None,
    reference: bool = False,
    resolved_reference: bool = False,
    weight: float = 1.0,
) -> None:
    entry = counts[attribute]
    actual_strict_tp = tp if strict_tp is None else strict_tp
    actual_strict_fn = fn if strict_fn is None else strict_fn
    entry["tp"] += tp
    entry["fp"] += fp
    entry["fn"] += fn
    entry["strict_tp"] += actual_strict_tp
    entry["strict_fn"] += actual_strict_fn
    entry["weighted_tp"] += tp * weight
    entry["weighted_fp"] += fp * weight
    entry["weighted_fn"] += fn * weight
    entry["weighted_strict_tp"] += actual_strict_tp * weight
    entry["weighted_strict_fn"] += actual_strict_fn * weight
    entry["precision_weight_squares"] += (tp + fp) * weight**2
    entry["recall_weight_squares"] += (tp + fn) * weight**2
    entry["strict_recall_weight_squares"] += (actual_strict_tp + actual_strict_fn) * weight**2
    if tp or fp or fn or strict_tp or strict_fn:
        entry["rows"].add(chunk_id)
    if reference:
        entry["reference_rows"].add(chunk_id)
        entry["reference_weights"][chunk_id] = weight
    if resolved_reference:
        entry["resolved_reference_rows"].add(chunk_id)
        entry["resolved_reference_weights"][chunk_id] = weight


def _kish_effective_size(weight_sum: float, weight_square_sum: float) -> float:
    return weight_sum**2 / weight_square_sum if weight_square_sum else 0.0


def _weighted_interval(
    success_weight: float,
    total_weight: float,
    weight_square_sum: float,
) -> tuple[list[float] | None, float]:
    n_eff = _kish_effective_size(total_weight, weight_square_sum)
    if not total_weight or not n_eff:
        return None, n_eff
    return wilson_interval(success_weight / total_weight * n_eff, n_eff), n_eff


def _metric(
    entry: dict,
    bucket_entries: dict[str, dict],
    partition: dict[str, int],
    sampled: dict[str, int],
    design_weighted: bool = False,
) -> dict:
    tp, fp, fn = entry["tp"], entry["fp"], entry["fn"]
    precision_n, recall_n = tp + fp, tp + fn
    weighted = bucket_weighted_recall(bucket_entries, partition, sampled)
    strict_tp, strict_fn = entry["strict_tp"], entry["strict_fn"]
    strict_n = strict_tp + strict_fn
    strict_bucket_entries = {
        bucket: {"tp": counts["strict_tp"], "fn": counts["strict_fn"]}
        for bucket, counts in bucket_entries.items()
    }
    strict_weighted = bucket_weighted_recall(strict_bucket_entries, partition, sampled)
    occurrences = len(entry["reference_rows"])
    resolved_occurrences = len(entry["resolved_reference_rows"])
    unweighted = {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "strict_tp": strict_tp,
        "strict_fn": strict_fn,
        "coverage": resolved_occurrences / occurrences if occurrences else None,
        "coverage_ci": wilson_interval(resolved_occurrences, occurrences),
        "precision": tp / precision_n if precision_n else None,
        "precision_ci": wilson_interval(tp, precision_n),
        "recall": tp / recall_n if recall_n else None,
        "recall_ci": wilson_interval(tp, recall_n),
        "weighted_recall": weighted,
        # Same approximation used by audit_tags; bootstrap if a gate result is borderline.
        "weighted_recall_ci": wilson_interval(weighted * recall_n, recall_n) if weighted is not None else None,
        "strict_recall": strict_tp / strict_n if strict_n else None,
        "strict_recall_ci": wilson_interval(strict_tp, strict_n),
        "strict_weighted_recall": strict_weighted,
        "strict_weighted_recall_ci": (
            wilson_interval(strict_weighted * strict_n, strict_n)
            if strict_weighted is not None else None
        ),
        "occurrences": occurrences,
        "resolved_occurrences": resolved_occurrences,
        "gated": occurrences >= 5,
    }
    if not design_weighted:
        return unweighted

    weighted_tp = entry["weighted_tp"]
    weighted_fp = entry["weighted_fp"]
    weighted_fn = entry["weighted_fn"]
    weighted_precision_n = weighted_tp + weighted_fp
    weighted_recall_n = weighted_tp + weighted_fn
    precision_ci, precision_n_eff = _weighted_interval(
        weighted_tp,
        weighted_precision_n,
        entry["precision_weight_squares"],
    )
    recall_ci, recall_n_eff = _weighted_interval(
        weighted_tp,
        weighted_recall_n,
        entry["recall_weight_squares"],
    )
    weighted_strict_tp = entry["weighted_strict_tp"]
    weighted_strict_fn = entry["weighted_strict_fn"]
    weighted_strict_n = weighted_strict_tp + weighted_strict_fn
    strict_recall_ci, strict_recall_n_eff = _weighted_interval(
        weighted_strict_tp,
        weighted_strict_n,
        entry["strict_recall_weight_squares"],
    )
    reference_weight = sum(entry["reference_weights"].values())
    resolved_reference_weight = sum(entry["resolved_reference_weights"].values())
    coverage_ci, coverage_n_eff = _weighted_interval(
        resolved_reference_weight,
        reference_weight,
        sum(weight**2 for weight in entry["reference_weights"].values()),
    )
    recall = weighted_tp / weighted_recall_n if weighted_recall_n else None
    strict_recall = weighted_strict_tp / weighted_strict_n if weighted_strict_n else None
    return {
        "tp": weighted_tp,
        "fp": weighted_fp,
        "fn": weighted_fn,
        "strict_tp": weighted_strict_tp,
        "strict_fn": weighted_strict_fn,
        "coverage": resolved_reference_weight / reference_weight if reference_weight else None,
        "coverage_ci": coverage_ci,
        "precision": weighted_tp / weighted_precision_n if weighted_precision_n else None,
        "precision_ci": precision_ci,
        "recall": recall,
        "recall_ci": recall_ci,
        "weighted_recall": recall,
        "weighted_recall_ci": recall_ci,
        "strict_recall": strict_recall,
        "strict_recall_ci": strict_recall_ci,
        "strict_weighted_recall": strict_recall,
        "strict_weighted_recall_ci": strict_recall_ci,
        "occurrences": occurrences,
        "resolved_occurrences": resolved_occurrences,
        "weighted_occurrences": reference_weight,
        "resolved_weighted_occurrences": resolved_reference_weight,
        "effective_sample_size": {
            "coverage": coverage_n_eff,
            "precision": precision_n_eff,
            "recall": recall_n_eff,
            "strict_recall": strict_recall_n_eff,
        },
        "gated": occurrences >= 5,
        "design_weighted": True,
        "unweighted": unweighted,
    }


def _metrics(
    counts: dict,
    counts_by_bucket: dict[str, dict],
    partition: dict[str, int],
    sampled: dict[str, int],
    design_weighted: bool = False,
) -> dict:
    return {
        attribute: _metric(
            entry,
            {bucket: bucket_counts[attribute] for bucket, bucket_counts in counts_by_bucket.items()},
            partition,
            sampled,
            design_weighted,
        )
        for attribute, entry in counts.items()
    }


def _design_weights(metadata: dict) -> dict[str, float] | None:
    design = metadata.get("design")
    if design is None:
        return None
    if not isinstance(design, dict) or design.get("name") != "cue" or not isinstance(design.get("strata"), dict):
        raise AuditError("sample_meta.json has an invalid cue design")
    chunks = metadata.get("chunks")
    if not isinstance(chunks, dict):
        raise AuditError("sample_meta.json has no chunk strata")
    if any(not isinstance(item, dict) or not isinstance(item.get("stratum"), str) for item in chunks.values()):
        raise AuditError("sample_meta.json has a cue-designed chunk without a stratum")
    sampled_by_stratum = Counter(item["stratum"] for item in chunks.values())
    weights = {}
    for stratum, values in design["strata"].items():
        if not isinstance(values, dict):
            raise AuditError(f"sample_meta.json has invalid design stratum {stratum}")
        population, sample = values.get("N_h"), values.get("n_h")
        if (
            not isinstance(population, int)
            or not isinstance(sample, int)
            or population <= 0
            or sample < 0
            or sample > population
            or sampled_by_stratum[stratum] != sample
        ):
            raise AuditError(f"sample_meta.json has invalid N_h/n_h for stratum {stratum}")
    unknown = sorted(set(sampled_by_stratum) - set(design["strata"]))
    if unknown:
        raise AuditError(f"sample_meta.json has unknown chunk strata: {', '.join(unknown)}")
    for chunk_id, values in chunks.items():
        stratum = values["stratum"]
        stratum_design = design["strata"][stratum]
        weights[chunk_id] = stratum_design["N_h"] / stratum_design["n_h"]
    return weights


def _unknown_share(
    records: list[dict],
    references: list[dict],
    metadata: dict,
    overrides: dict[tuple[str, str], set[str]],
    excluded: set[tuple[str, str]],
    weights: dict[str, float] | None = None,
) -> dict:
    reference_by_id = {row["chunk_id"]: row for row in references}
    unknown_records = [row for row in records if row.get("condition_status") == "unknown"]
    conditioned = 0
    conditioned_weight = 0.0
    attributes: Counter[str] = Counter()
    for record in unknown_records:
        chunk_id = record["chunk_id"]
        reference = reference_by_id[chunk_id]
        present = {
            attribute
            for attribute in CONSTRAINT_ATTRIBUTES
            if (chunk_id, attribute) not in excluded
            and overrides.get((chunk_id, attribute), _values(reference, attribute))
        }
        if present:
            conditioned += 1
            conditioned_weight += weights.get(chunk_id, 1.0) if weights is not None else 1.0
            attributes.update(present)

    sampled_unknown = len(unknown_records)
    sampled_unknown_weight = sum(
        weights.get(row["chunk_id"], 1.0) if weights is not None else 1.0
        for row in unknown_records
    )
    if weights is None:
        share = conditioned / sampled_unknown if sampled_unknown else None
        share_ci = wilson_interval(conditioned, sampled_unknown)
        share_n_eff = float(sampled_unknown)
    else:
        share = conditioned_weight / sampled_unknown_weight if sampled_unknown_weight else None
        share_ci, share_n_eff = _weighted_interval(
            conditioned_weight,
            sampled_unknown_weight,
            sum(weights[row["chunk_id"]] ** 2 for row in unknown_records),
        )
    index_unknown = sum(metadata["bucket_partition"].get(bucket, 0) for bucket in UNKNOWN_BUCKETS)
    result = {
        "sampled_unknown_chunks": sampled_unknown,
        "reference_conditioned_chunks": conditioned,
        "share": share,
        "share_ci": share_ci,
        "index_unknown_chunks": index_unknown,
        "estimated_conditioned_chunks": share * index_unknown if share is not None else None,
        "estimated_conditioned_chunks_ci": (
            [bound * index_unknown for bound in share_ci] if share_ci is not None else None
        ),
        "top_attributes": dict(sorted(attributes.items(), key=lambda item: (-item[1], item[0]))[:5]),
    }
    if weights is not None:
        result.update(
            weighted_sampled_unknown_chunks=sampled_unknown_weight,
            weighted_reference_conditioned_chunks=conditioned_weight,
            share_effective_sample_size=share_n_eff,
            unweighted={
                "share": conditioned / sampled_unknown if sampled_unknown else None,
                "share_ci": wilson_interval(conditioned, sampled_unknown),
            },
        )
    return result


def score_comparison(
    records: list[dict],
    references: list[dict],
    metadata: dict,
    overrides: dict[tuple[str, str], set[str]] | None = None,
    excluded: set[tuple[str, str]] | None = None,
) -> dict:
    """Compare resolved values and retain unknown references as strict misses.

    Example: TP=4, FP=2, FN=3 gives resolved P=4/6 and R=4/7. Predicted
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
    weights = _design_weights(metadata)
    design_weighted = weights is not None
    applicant_errors = {
        error: {"count": 0, "total": 0, "weighted": 0.0, "weighted_total": 0.0}
        for error in ("fp", "fn")
    }
    any_of_all = any_of_all_correct = any_of_present = any_of_present_correct = 0

    for record in records:
        chunk_id = record["chunk_id"]
        predicted = record.get("applicability") or {}
        reference = reference_by_id[chunk_id]
        bucket, campus = record["tag_bucket"], record["_campus"]
        weight = weights[chunk_id] if weights is not None else 1.0
        applicant_chunk = "applicant" in _values(predicted, "academic_status")
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
            resolved = attribute in ALWAYS_RESOLVED or record.get("condition_status") != "unknown"
            resolved_tp, resolved_fp, resolved_fn = (tp, fp, fn) if resolved else (0, 0, 0)
            strict_tp, strict_fn = (tp, fn) if resolved else (0, len(ref))
            add_kwargs = {
                "strict_tp": strict_tp,
                "strict_fn": strict_fn,
                "reference": bool(ref),
                "resolved_reference": bool(ref) and resolved,
                "weight": weight,
            }
            _add(overall, attribute, chunk_id, resolved_tp, resolved_fp, resolved_fn, **add_kwargs)
            _add(by_bucket[bucket], attribute, chunk_id, resolved_tp, resolved_fp, resolved_fn, **add_kwargs)
            _add(by_campus[campus], attribute, chunk_id, resolved_tp, resolved_fp, resolved_fn, **add_kwargs)
            _add(
                by_campus_bucket[campus][bucket],
                attribute,
                chunk_id,
                resolved_tp,
                resolved_fp,
                resolved_fn,
                **add_kwargs,
            )
            if resolved and (tp or fp):
                method = methods.get("any_of") if any(attribute in group for group in predicted.get("any_of") or []) else methods.get(attribute)
                family = _method_family(method, bucket)
                method_kwargs = {
                    "strict_tp": tp,
                    "strict_fn": 0,
                    "reference": bool(tp),
                    "resolved_reference": bool(tp),
                    "weight": weight,
                }
                _add(by_method[family], attribute, chunk_id, tp, fp, 0, **method_kwargs)
                _add(by_method_bucket[family][bucket], attribute, chunk_id, tp, fp, 0, **method_kwargs)
            if resolved and fn:
                family = _method_family(None, bucket)
                method_kwargs = {
                    "strict_tp": 0,
                    "strict_fn": fn,
                    "reference": True,
                    "resolved_reference": True,
                    "weight": weight,
                }
                _add(by_method[family], attribute, chunk_id, 0, 0, fn, **method_kwargs)
                _add(by_method_bucket[family][bucket], attribute, chunk_id, 0, 0, fn, **method_kwargs)
            elif not resolved and ref:
                family = _method_family(None, bucket)
                method_kwargs = {
                    "strict_tp": 0,
                    "strict_fn": len(ref),
                    "reference": True,
                    "resolved_reference": False,
                    "weight": weight,
                }
                _add(by_method[family], attribute, chunk_id, 0, 0, 0, **method_kwargs)
                _add(by_method_bucket[family][bucket], attribute, chunk_id, 0, 0, 0, **method_kwargs)
            if attribute == "degree_level":
                for error, count in (("fp", resolved_fp), ("fn", resolved_fn)):
                    applicant_errors[error]["total"] += count
                    applicant_errors[error]["weighted_total"] += count * weight
                    if applicant_chunk:
                        applicant_errors[error]["count"] += count
                        applicant_errors[error]["weighted"] += count * weight

    partition = metadata["bucket_partition"]
    per_attribute = _metrics(overall, by_bucket, partition, sampled, design_weighted)
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
            family: _metrics(counts, by_method_bucket[family], partition, sampled, design_weighted)
            for family, counts in by_method.items()
        },
        "by_bucket": {
            bucket: _metrics(counts, {bucket: counts}, partition, sampled, design_weighted)
            for bucket, counts in by_bucket.items()
        },
        "by_campus": {
            campus: _metrics(counts, by_campus_bucket[campus], partition, sampled, design_weighted)
            for campus, counts in by_campus.items()
        },
        "any_of_exact_match": {
            "all_chunks": {"matches": any_of_all_correct, "n": any_of_all, "rate": any_of_all_correct / any_of_all if any_of_all else None},
            "chunks_with_any_of": {"matches": any_of_present_correct, "n": any_of_present, "rate": any_of_present_correct / any_of_present if any_of_present else None},
        },
        "unknown_share": _unknown_share(records, references, metadata, overrides, excluded, weights),
        "applicant_chunk_degree_errors": {
            error: {
                "count": values["count"],
                "total": values["total"],
                "weighted_share": (
                    values["weighted"] / values["weighted_total"]
                    if values["weighted_total"]
                    else None
                ),
            }
            for error, values in applicant_errors.items()
        },
        "sampling_design": metadata.get("design", {}).get("name"),
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


def _format_count(value: float | int) -> str:
    return str(value) if isinstance(value, int) else f"{value:.3f}"


def _append_table(lines: list[str], metrics: dict, gate: bool = False) -> None:
    design_weighted = any(metric.get("design_weighted") for metric in metrics.values())
    if design_weighted:
        lines.extend(["Design-weighted values (inverse stratum inclusion probability):", ""])
    if gate:
        lines.extend(
            [
                "| Attribute | Occurrences | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) | Result |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---|",
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
                f"| {attribute} | {metric['occurrences']}"
                + (
                    f" (weighted {_format_count(metric['weighted_occurrences'])})"
                    if metric.get("design_weighted")
                    else ""
                )
                + " | "
                f"{_format_metric(metric['coverage'], metric['coverage_ci'])} | "
                f"{_format_metric(metric['precision'], metric['precision_ci'])} | "
                f"{_format_metric(metric['recall'], metric['recall_ci'])} | "
                f"{_format_metric(metric['weighted_recall'], metric['weighted_recall_ci'])} | "
                f"{_format_metric(metric['strict_recall'], metric['strict_recall_ci'])} | "
                f"{_format_metric(metric['strict_weighted_recall'], metric['strict_weighted_recall_ci'])} | "
                f"{'PASS' if passed else 'FAIL'} |"
            )
    else:
        lines.extend(
            [
                "| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for attribute, metric in metrics.items():
            lines.append(
                f"| {attribute} | {metric['occurrences']} | {_format_count(metric['tp'])} | "
                f"{_format_count(metric['fp'])} | {_format_count(metric['fn'])} | "
                f"{_format_metric(metric['coverage'], metric['coverage_ci'])} | "
                f"{_format_metric(metric['precision'], metric['precision_ci'])} | "
                f"{_format_metric(metric['recall'], metric['recall_ci'])} | "
                f"{_format_metric(metric['weighted_recall'], metric['weighted_recall_ci'])} | "
                f"{_format_metric(metric['strict_recall'], metric['strict_recall_ci'])} | "
                f"{_format_metric(metric['strict_weighted_recall'], metric['strict_weighted_recall_ci'])} |"
            )
    if design_weighted:
        lines.extend(
            [
                "",
                "Unweighted sample values:",
                "",
                "| Attribute | TP | FP | FN | Coverage (95% CI) | Precision (95% CI) | Recall (95% CI) | Strict recall (95% CI) |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for attribute, metric in metrics.items():
            if gate and not metric["gated"]:
                continue
            raw = metric["unweighted"]
            lines.append(
                f"| {attribute} | {raw['tp']} | {raw['fp']} | {raw['fn']} | "
                f"{_format_metric(raw['coverage'], raw['coverage_ci'])} | "
                f"{_format_metric(raw['precision'], raw['precision_ci'])} | "
                f"{_format_metric(raw['recall'], raw['recall_ci'])} | "
                f"{_format_metric(raw['strict_recall'], raw['strict_recall_ci'])} |"
            )


def _append_unknown_share(lines: list[str], unknown: dict) -> None:
    lines.extend(["", "## Unknown-condition estimate", ""])
    share = _format_metric(unknown["share"], unknown["share_ci"])
    estimate = unknown["estimated_conditioned_chunks"]
    estimate_ci = unknown["estimated_conditioned_chunks_ci"]
    if "unweighted" in unknown:
        lines.append(
            "Reference-conditioned unknown chunks: "
            f"{unknown['reference_conditioned_chunks']}/{unknown['sampled_unknown_chunks']}; "
            f"design-weighted sums {_format_count(unknown['weighted_reference_conditioned_chunks'])}/"
            f"{_format_count(unknown['weighted_sampled_unknown_chunks'])} ({share})."
        )
        lines.append(
            "Unweighted sample share: "
            f"{_format_metric(unknown['unweighted']['share'], unknown['unweighted']['share_ci'])}."
        )
    else:
        lines.append(
            f"Reference-conditioned unknown chunks: {unknown['reference_conditioned_chunks']}/"
            f"{unknown['sampled_unknown_chunks']} ({share})."
        )
    if estimate is None or estimate_ci is None:
        lines.append(f"Estimated conditioned chunks among {unknown['index_unknown_chunks']} index unknowns: null.")
    else:
        lines.append(
            f"Estimated conditioned chunks among {unknown['index_unknown_chunks']} index unknowns: "
            f"{estimate:.1f} [{estimate_ci[0]:.1f}, {estimate_ci[1]:.1f}]."
        )
    top = unknown["top_attributes"]
    lines.append(
        "Top attributes: "
        + (", ".join(f"{attribute} ({count})" for attribute, count in top.items()) if top else "none")
        + "."
    )


def scores_markdown(scores: dict, final: bool = False) -> str:
    lines = [LIMITATION, "", "# Automated applicability tag audit", "", "## G2", ""]
    _append_table(lines, scores["per_attribute"], gate=True)
    lines.extend(["", f"G2 verdict: **{'PASS' if scores['g2']['passed'] else 'FAIL'}**."])
    _append_unknown_share(lines, scores["unknown_share"])
    errors = scores["applicant_chunk_degree_errors"]
    lines.extend(
        [
            "",
            "## Degree-level errors in applicant-tagged chunks",
            "",
            "| Error | Applicant units | All units | Design-weighted share |",
            "|---|---:|---:|---:|",
        ]
    )
    for error in ("fp", "fn"):
        values = errors[error]
        share = "null" if values["weighted_share"] is None else f"{values['weighted_share']:.3f}"
        lines.append(f"| {error.upper()} | {values['count']} | {values['total']} | {share} |")
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
                f"Carried decisions: {review.get('carried', 0)}.",
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


def _read_disagreement_key(path: Path) -> dict:
    try:
        key = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"Cannot read disagreement key {path}: {exc}") from exc
    if not isinstance(key, dict) or not isinstance(key.get("rows"), list):
        raise AuditError(f"Disagreement key {path} is invalid")
    return key


def _disagreement_values(row: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return tuple(sorted((tuple(sorted(row["value_a"])), tuple(sorted(row["value_b"])))))


def carry_disagreement_decisions(
    source: Path, disagreements: list[dict]
) -> tuple[list[dict], list[dict], list[dict]]:
    old_disagreements, errors = _read_jsonl(source / "disagreements.jsonl", "disagreements")
    for row in old_disagreements:
        row.pop("_line", None)
    if errors:
        raise ReferenceValidationError(errors)
    old_key = _read_disagreement_key(source / "disagreements_key.json")
    read_decisions(source / "decisions.jsonl", old_disagreements, old_key)
    decision_rows, errors = _read_jsonl(source / "decisions.jsonl", "decisions")
    if errors:
        raise ReferenceValidationError(errors)

    old_by_pair = {(row["chunk_id"], row["attribute"]): row for row in old_disagreements}
    decision_by_pair = {(row["chunk_id"], row["attribute"]): row for row in decision_rows}
    new_rows, carried_rows, carried_decisions = [], [], []
    for row in disagreements:
        pair = (row["chunk_id"], row["attribute"])
        old = old_by_pair.get(pair)
        decision = decision_by_pair.get(pair)
        if old is None or decision is None or _disagreement_values(old) != _disagreement_values(row):
            new_rows.append(row)
            continue
        carried = {field: value for field, value in decision.items() if field != "_line"}
        if carried["decision"] in {"a", "b"}:
            chosen = old[f"value_{carried['decision']}"]
            carried["decision"] = "a" if chosen == row["value_a"] else "b"
        carried.update(value_a=row["value_a"], value_b=row["value_b"])
        carried_rows.append(row)
        carried_decisions.append(carried)
    return new_rows, carried_rows, carried_decisions


def write_comparison(
    out: Path,
    scores: dict,
    disagreements: list[dict],
    key: dict,
    carried_disagreements: list[dict] | None = None,
    carried_decisions: list[dict] | None = None,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "disagreements.jsonl", disagreements)
    _write_jsonl(out / "carried_disagreements.jsonl", carried_disagreements or [])
    _write_jsonl(out / "carried_decisions.jsonl", carried_decisions or [])
    (out / "disagreements_key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    (out / "scores_raw.json").write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    (out / "scores_raw.md").write_text(scores_markdown(scores), encoding="utf-8")


def compare(
    db: Database,
    index_id: str,
    reference_path: Path,
    out: Path,
    carry_decisions: Path | None = None,
) -> dict:
    metadata = read_sample_metadata(out / "sample_meta.json", index_id)
    records = load_records(db, metadata["chunk_ids"])
    references = validate_reference(reference_path, records, metadata["chunk_ids"])
    scores = score_comparison(records, references, metadata)
    disagreements, key = disagreement_rows(records, references, metadata["seed"])
    carried_disagreements: list[dict] = []
    carried: list[dict] = []
    if carry_decisions is not None:
        disagreements, carried_disagreements, carried = carry_disagreement_decisions(
            carry_decisions, disagreements
        )
    scores["carried_decisions"] = len(carried)
    write_comparison(out, scores, disagreements, key, carried_disagreements, carried)
    return scores


def _decision_values(attribute: str, values: Any, prefix: str, errors: list[str]) -> set[str]:
    if not _valid_attribute_values(attribute, values):
        errors.append(f"{prefix} correct_values: invalid values for {attribute}: {values!r}")
        return set()
    return set(values)


def read_decisions(
    path: Path,
    disagreements: list[dict],
    key: dict,
    carried_path: Path | None = None,
) -> tuple[dict, set, dict, list[dict]]:
    rows, errors = _read_jsonl(path, "decisions")
    if carried_path is not None:
        carried, carried_errors = _read_jsonl(carried_path, "carried decisions")
        rows.extend(carried)
        errors.extend(carried_errors)
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
    carried_disagreements_path = out / "carried_disagreements.jsonl"
    carried_decisions_path = out / "carried_decisions.jsonl"
    carried_disagreements = []
    if carried_disagreements_path.exists():
        carried_disagreements, errors = _read_jsonl(carried_disagreements_path, "carried disagreements")
        if errors:
            raise ReferenceValidationError(errors)
        for row in carried_disagreements:
            row.pop("_line", None)
    all_disagreements = disagreements + carried_disagreements
    key = _read_disagreement_key(out / "disagreements_key.json")
    overrides, excluded, summary, ambiguous = read_decisions(
        decisions_path,
        all_disagreements,
        key,
        carried_decisions_path if carried_decisions_path.exists() else None,
    )
    summary["carried"] = len(carried_disagreements)
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


def _load_final_scores(folder: Path) -> dict:
    path = folder / "scores_final.json"
    try:
        scores = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"Cannot read final scores {path}: {exc}") from exc
    if not isinstance(scores, dict) or not isinstance(scores.get("per_attribute"), dict):
        raise AuditError(f"Final scores {path} have no per_attribute metrics")
    if not isinstance(scores.get("unknown_share"), dict):
        raise AuditError(f"Final scores {path} have no unknown_share metrics")
    return scores


def _gate_result(metric: dict) -> str:
    if not metric.get("gated"):
        return "N/A"
    passed = (
        metric.get("precision") is not None and metric["precision"] >= 0.8
        and metric.get("weighted_recall") is not None and metric["weighted_recall"] >= 0.7
    )
    return "PASS" if passed else "FAIL"


def _side_metric(metric: dict, field: str, interval_field: str) -> str:
    value = _format_metric(metric[field], metric[interval_field])
    if metric.get("design_weighted"):
        raw = metric["unweighted"]
        raw_field, raw_interval = (
            ("recall", "recall_ci")
            if field == "weighted_recall"
            else (field, interval_field)
        )
        value += f"; unweighted {_format_metric(raw[raw_field], raw[raw_interval])}"
    return value


def side_by_side_report(
    folders: list[Path],
    destination: Path,
    labels: list[str] | None = None,
) -> None:
    if len(folders) < 2:
        raise AuditError("--side-by-side requires at least two audit folders")
    if labels and len(labels) != len(folders):
        raise AuditError("The number of --label values must match the audit folders")
    labels = labels or [chr(ord("A") + index) for index in range(len(folders))]
    if len(set(labels)) != len(labels):
        raise AuditError("--label values must be unique")
    score_sets = [_load_final_scores(folder) for folder in folders]
    attributes = score_sets[0]["per_attribute"]
    if any(set(scores["per_attribute"]) != set(attributes) for scores in score_sets[1:]):
        raise AuditError("Side-by-side audit folders have different attribute rows")

    lines = [
        LIMITATION,
        "",
        "# G2b side-by-side audit",
        "",
    ]
    lines.extend(
        f"{label}{' (gate sample)' if index == len(folders) - 1 else ''}: `{folder}`  "
        for index, (label, folder) in enumerate(zip(labels, folders))
    )
    lines.extend(["", "Cue-designed cells show design-weighted values first and unweighted sample values second.", ""])
    columns = [
        f"{label} {name}"
        for label in labels
        for name in ("occurrences", "coverage", "precision", "recall", "weighted recall", "strict recall", "gate")
    ]
    lines.extend(
        [
            "| Attribute | " + " | ".join(columns) + " |",
            "|---|" + "|".join("---:" if not column.endswith("gate") else "---" for column in columns) + "|",
        ]
    )
    for attribute in ATTRIBUTES:
        if attribute not in attributes:
            continue
        cells = [attribute]
        for scores in score_sets:
            metric = scores["per_attribute"][attribute]
            occurrence = str(metric["occurrences"])
            if metric.get("design_weighted"):
                occurrence += f"; weighted {_format_count(metric['weighted_occurrences'])}"
            cells.extend(
                [
                    occurrence,
                    _side_metric(metric, "coverage", "coverage_ci"),
                    _side_metric(metric, "precision", "precision_ci"),
                    _side_metric(metric, "recall", "recall_ci"),
                    _side_metric(metric, "weighted_recall", "weighted_recall_ci"),
                    _side_metric(metric, "strict_recall", "strict_recall_ci"),
                    _gate_result(metric),
                ]
            )
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Unknown-condition estimate",
            "",
            "| Audit | Sampled unknown | Reference-conditioned | Share (95% CI) | Index unknown | Estimated conditioned (95% CI) | Top attributes |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for label, scores in zip(labels, score_sets):
        unknown = scores["unknown_share"]
        estimate = unknown["estimated_conditioned_chunks"]
        estimate_ci = unknown["estimated_conditioned_chunks_ci"]
        estimate_text = (
            "null [null]"
            if estimate is None or estimate_ci is None
            else f"{estimate:.1f} [{estimate_ci[0]:.1f}, {estimate_ci[1]:.1f}]"
        )
        top = ", ".join(
            f"{attribute} ({count})" for attribute, count in unknown["top_attributes"].items()
        ) or "none"
        share = _format_metric(unknown["share"], unknown["share_ci"])
        if "unweighted" in unknown:
            share += "; unweighted " + _format_metric(
                unknown["unweighted"]["share"],
                unknown["unweighted"]["share_ci"],
            )
        lines.append(
            f"| {label} | {unknown['sampled_unknown_chunks']} | "
            f"{unknown['reference_conditioned_chunks']} | "
            f"{share} | "
            f"{unknown['index_unknown_chunks']} | {estimate_text} | {top} |"
        )

    lines.extend(
        [
            "",
            "## Degree-level errors in applicant-tagged chunks",
            "",
            "| Audit | Applicant FP / all FP | FP design-weighted share | Applicant FN / all FN | FN design-weighted share |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, scores in zip(labels, score_sets):
        errors = scores.get("applicant_chunk_degree_errors")
        if not errors:
            lines.append(f"| {label} | N/A | N/A | N/A | N/A |")
            continue
        fp, fn = errors["fp"], errors["fn"]
        fp_share = "null" if fp["weighted_share"] is None else f"{fp['weighted_share']:.3f}"
        fn_share = "null" if fn["weighted_share"] is None else f"{fn['weighted_share']:.3f}"
        lines.append(
            f"| {label} | {fp['count']} / {fp['total']} | {fp_share} | "
            f"{fn['count']} / {fn['total']} | {fn_share} |"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def connect_index(index_id: str) -> Database:
    return Database.connect(get_settings()).for_index(index_id)


def _quota(value: str) -> tuple[str, int]:
    bucket, separator, count_text = value.partition("=")
    if not separator or bucket not in BUCKETS:
        choices = ", ".join(BUCKETS)
        raise argparse.ArgumentTypeError(f"quota must be BUCKET=N, where BUCKET is one of {choices}")
    try:
        count = int(count_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("quota N must be a non-negative integer") from exc
    if count < 0:
        raise argparse.ArgumentTypeError("quota N must be a non-negative integer")
    return bucket, count


def _quotas(values: list[tuple[str, int]]) -> dict[str, int]:
    counts = Counter(bucket for bucket, _ in values)
    duplicates = sorted(bucket for bucket, count in counts.items() if count > 1)
    if duplicates:
        raise AuditError(f"Duplicate --quota buckets: {', '.join(duplicates)}")
    return dict(values)


def _minimum_cue(value: str) -> tuple[str, int]:
    cue, separator, count_text = value.partition("=")
    if not separator or cue not in CUES:
        choices = ", ".join(CUES)
        raise argparse.ArgumentTypeError(f"minimum must be CUE=N, where CUE is one of {choices}")
    try:
        count = int(count_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("minimum N must be a non-negative integer") from exc
    if count < 0:
        raise argparse.ArgumentTypeError("minimum N must be a non-negative integer")
    return cue, count


def _cue_minimums(values: list[tuple[str, int]]) -> dict[str, int]:
    counts = Counter(cue for cue, _ in values)
    duplicates = sorted(cue for cue, count in counts.items() if count > 1)
    if duplicates:
        raise AuditError(f"Duplicate --min-cue values: {', '.join(duplicates)}")
    return dict(values)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the blind automated AAES tag audit")
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample", help="write the stratified blind sample")
    sample.add_argument("--index-id", required=True)
    sample.add_argument("--n", type=int, default=150)
    sample.add_argument("--seed", type=int, default=20261111)
    sample.add_argument("--quota", type=_quota, action="append", default=[], metavar="BUCKET=N")
    sample.add_argument("--design", choices=("cue",))
    sample.add_argument("--min-cue", type=_minimum_cue, action="append", default=[], metavar="CUE=N")
    sample.add_argument("--force", action="store_true")
    sample_source = sample.add_mutually_exclusive_group()
    sample_source.add_argument("--exclude", type=Path, action="append", default=[])
    sample_source.add_argument("--reuse", type=Path)
    compare_parser = commands.add_parser("compare", help="validate and compare a blind reference")
    compare_parser.add_argument("--index-id", required=True)
    compare_parser.add_argument("--reference", type=Path, required=True)
    compare_parser.add_argument("--carry-decisions", type=Path)
    finalize_parser = commands.add_parser("finalize", help="apply blind disagreement decisions and re-score")
    finalize_parser.add_argument("--index-id", required=True)
    finalize_parser.add_argument("--reference", type=Path, required=True)
    finalize_parser.add_argument("--decisions", type=Path, required=True)
    report = commands.add_parser("report", help="compare finalized audit folders")
    report.add_argument("--side-by-side", type=Path, nargs="+", required=True, metavar="OUT")
    report.add_argument("--label", action="append", default=[])
    report.add_argument("--to", type=Path, required=True)
    for command in (sample, compare_parser, finalize_parser):
        command.add_argument("--out", default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "report":
            side_by_side_report(args.side_by_side, args.to, args.label)
            print(f"Wrote side-by-side report to {args.to}")
            return 0
        out = output_dir(args.index_id, args.out)
        db = connect_index(args.index_id)
        if args.command == "sample":
            quotas = _quotas(args.quota)
            minimums = _cue_minimums(args.min_cue)
            if minimums and args.design != "cue":
                raise AuditError("--min-cue requires --design cue")
            if args.design and quotas:
                raise AuditError("--quota cannot be combined with --design")
            if args.reuse and (quotas or args.design or minimums):
                raise AuditError("--quota, --design and --min-cue cannot be combined with --reuse")
            partition = manifest_bucket_partition(db)
            if args.reuse:
                source_metadata, chunk_ids = sample_chunk_ids(args.reuse)
                records = load_records(db, chunk_ids)
                targets = {bucket: sum(row["tag_bucket"] == bucket for row in records) for bucket in BUCKETS}
                seed = source_metadata.get("seed")
                if not isinstance(seed, int):
                    raise AuditError(f"Sample metadata {args.reuse} has no valid seed")
                metadata = sample_metadata(
                    args.index_id,
                    seed,
                    records,
                    targets,
                    partition,
                    reused_from=args.reuse,
                )
                write_reused_sample(records, metadata, args.reuse, out, args.force)
            else:
                available = load_records(db)
                excluded_ids: set[str] = set()
                excluded_files = []
                for path in args.exclude:
                    _, chunk_ids = sample_chunk_ids(path)
                    excluded_ids.update(chunk_ids)
                    excluded_files.append({"path": str(path), "count": len(chunk_ids)})
                available = [row for row in available if row["chunk_id"] not in excluded_ids]
                design = None
                if args.design == "cue":
                    records, design = sample_cue_records(available, args.n, args.seed, minimums)
                    targets = {
                        bucket: sum(row["tag_bucket"] == bucket for row in records)
                        for bucket in BUCKETS
                    }
                else:
                    records, targets = sample_records(available, args.n, args.seed, quotas)
                overlap = sorted({row["chunk_id"] for row in records} & excluded_ids)
                if overlap:
                    raise AuditError(f"Sample overlaps excluded chunks: {', '.join(overlap)}")
                metadata = sample_metadata(
                    args.index_id,
                    args.seed,
                    records,
                    targets,
                    partition,
                    available_records=available,
                    excluded_files=excluded_files,
                    design=design,
                )
                write_sample(records, metadata, out, args.force)
            print(json.dumps(metadata["achieved_strata"], indent=2))
            print(f"Wrote {len(records)} blind chunks to {out}")
        elif args.command == "compare":
            scores = compare(db, args.index_id, args.reference, out, args.carry_decisions)
            print(f"G2 raw: {'PASS' if scores['g2']['passed'] else 'FAIL'}")
            print(f"Carried {scores['carried_decisions']} disagreement decisions")
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
