"""Validate and summarize question drafts without reading page bodies."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from app.config import DATA_DIR
from typing import Any


SLICES = {"unconditional", "conditional", "temporal", "negative", "multi_session"}
CAMPUSES = {"seoul", "erica"}
ATTRIBUTES = {
    "campus",
    "degree_level",
    "year",
    "student_type",
    "visa",
    "topik_level",
    "english_track",
    "academic_status",
    "korean_standard",
}
ANSWERABILITIES = {
    "answerable",
    "partial",
    "unanswerable",
    "external_only",
    "korean_only",
    "unanswerable_unreadable",
}
FIELDS = {
    "draft_id",
    "slice",
    "campus",
    "persona_id",
    "topic_doc_ids",
    "question",
    "session_history",
    "intended_attributes",
    "intended_answerability",
    "why",
    "annotator",
    "origin",
}
QUOTAS = {
    ("unconditional", "seoul"): 48,
    ("unconditional", "erica"): 32,
    ("conditional", "seoul"): 32,
    ("conditional", "erica"): 25,
    ("temporal", "seoul"): 17,
    ("temporal", "erica"): 7,
    ("negative", "seoul"): 28,
    ("negative", "erica"): 18,
    ("multi_session", "seoul"): 13,
    ("multi_session", "erica"): 10,
}


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
                continue
            if not isinstance(row, dict):
                errors.append(f"line {line_number}: row must be a JSON object")
                continue
            rows.append(row)
    return rows, errors


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_unreadable_topic(topic: dict[str, Any]) -> bool:
    if topic.get("file_type") == "hwp":
        return True
    text = " ".join([str(topic.get("title", "")), *topic.get("headings", [])]).lower()
    return topic.get("file_type") == "pdf" and ("scan" in text or "image-only" in text)


def validate_drafts(
    drafts_path: Path, topics_path: Path, personas_path: Path
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return parsed rows and every schema/reference error."""
    topics, topic_errors = _load_jsonl(topics_path)
    drafts, errors = _load_jsonl(drafts_path)
    errors[:0] = [f"topics: {error}" for error in topic_errors]
    personas = _load_json(personas_path)

    topics_by_id = {row.get("doc_id"): row for row in topics}
    topic_ids = set(topics_by_id)
    persona_campuses = {
        row.get("persona_id"): row.get("gold_profile", {}).get("campus")
        for row in personas
        if isinstance(row, dict)
    }
    seen_ids: set[str] = set()

    for line_number, row in enumerate(drafts, 1):
        prefix = f"line {line_number}"
        missing = FIELDS - row.keys()
        extra = row.keys() - FIELDS
        if missing:
            errors.append(f"{prefix}: missing fields: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{prefix}: unknown fields: {', '.join(sorted(extra))}")
        if missing:
            continue

        draft_id = row["draft_id"]
        if not isinstance(draft_id, str) or not draft_id.strip():
            errors.append(f"{prefix}: draft_id must be a non-empty string")
        elif draft_id in seen_ids:
            errors.append(f"{prefix}: duplicate draft_id {draft_id!r}")
        else:
            seen_ids.add(draft_id)

        if not isinstance(row["slice"], str) or row["slice"] not in SLICES:
            errors.append(f"{prefix}: unknown slice {row['slice']!r}")
        if not isinstance(row["campus"], str) or row["campus"] not in CAMPUSES:
            errors.append(f"{prefix}: unknown campus {row['campus']!r}")

        persona_id = row["persona_id"]
        if not isinstance(persona_id, str) or persona_id not in persona_campuses:
            errors.append(f"{prefix}: unknown persona_id {persona_id!r}")
        elif row["campus"] != persona_campuses[persona_id]:
            errors.append(f"{prefix}: campus does not match persona {persona_id!r}")

        doc_ids = row["topic_doc_ids"]
        if not _is_string_list(doc_ids) or not 1 <= len(doc_ids) <= 3:
            errors.append(f"{prefix}: topic_doc_ids must contain 1-3 strings")
        else:
            for doc_id in doc_ids:
                if doc_id not in topic_ids:
                    errors.append(f"{prefix}: unknown topic doc_id {doc_id!r}")

        for field in ("question", "why"):
            if not isinstance(row[field], str) or not row[field].strip():
                errors.append(f"{prefix}: {field} must be a non-empty string")

        history = row["session_history"]
        if not _is_string_list(history):
            errors.append(f"{prefix}: session_history must be a list of strings")
        elif row["slice"] == "multi_session" and not 1 <= len(history) <= 3:
            errors.append(f"{prefix}: multi_session history must contain 1-3 turns")
        elif row["slice"] != "multi_session" and history:
            errors.append(f"{prefix}: session_history must be empty outside multi_session")

        attributes = row["intended_attributes"]
        if not _is_string_list(attributes):
            errors.append(f"{prefix}: intended_attributes must be a list of strings")
        elif len(attributes) != len(set(attributes)):
            errors.append(f"{prefix}: intended_attributes contains duplicates")
        else:
            for attribute in attributes:
                if attribute not in ATTRIBUTES:
                    errors.append(f"{prefix}: unknown intended attribute {attribute!r}")

        answerability = row["intended_answerability"]
        if not isinstance(answerability, str) or answerability not in ANSWERABILITIES:
            errors.append(
                f"{prefix}: unknown intended_answerability "
                f"{answerability!r}"
            )
        elif _is_string_list(doc_ids) and all(doc_id in topics_by_id for doc_id in doc_ids):
            selected_topics = [topics_by_id[doc_id] for doc_id in doc_ids]
            if answerability == "korean_only" and not all(
                topic.get("korean_only") is True for topic in selected_topics
            ):
                errors.append(f"{prefix}: korean_only requires korean_only topics")
            if answerability == "unanswerable_unreadable" and not all(
                _is_unreadable_topic(topic) for topic in selected_topics
            ):
                errors.append(
                    f"{prefix}: unanswerable_unreadable requires hwp or scanned PDF topics"
                )
        annotator = row["annotator"]
        if (
            not isinstance(annotator, str)
            or not annotator.startswith("codex:")
            or not annotator.removeprefix("codex:").strip()
        ):
            errors.append(f"{prefix}: annotator must be 'codex:<model>'")
        if row["origin"] != "agent_draft":
            errors.append(f"{prefix}: origin must be 'agent_draft'")

    return drafts, errors


def print_counts(rows: list[dict[str, Any]]) -> None:
    slice_campus = Counter((row.get("slice"), row.get("campus")) for row in rows)
    personas = Counter(row.get("persona_id") for row in rows)
    answerabilities = Counter(row.get("intended_answerability") for row in rows)

    print("Slice x campus (count/quota)")
    for slice_name in ("unconditional", "conditional", "temporal", "negative", "multi_session"):
        values = []
        for campus in ("seoul", "erica"):
            count = slice_campus[(slice_name, campus)]
            values.append(f"{campus}={count}/{QUOTAS[(slice_name, campus)]}")
        print(f"  {slice_name}: {', '.join(values)}")

    print("Per persona")
    for persona_id, count in sorted(personas.items(), key=lambda item: str(item[0])):
        print(f"  {persona_id}: {count}")

    print("Per intended answerability")
    for answerability, count in sorted(answerabilities.items(), key=lambda item: str(item[0])):
        print(f"  {answerability}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="validate and summarize question drafts")
    check.add_argument(
        "--drafts",
        type=Path,
        default=DATA_DIR / "HYU/labels/drafts/questions_codex.jsonl",
    )
    check.add_argument(
        "--topics", type=Path, default=DATA_DIR / "HYU/labels/topics.jsonl"
    )
    check.add_argument(
        "--personas", type=Path, default=DATA_DIR / "HYU/labels/personas.json"
    )
    args = parser.parse_args()

    rows, errors = validate_drafts(args.drafts, args.topics, args.personas)
    print_counts(rows)
    if errors:
        print("Schema errors")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"OK: {len(rows)} drafts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
