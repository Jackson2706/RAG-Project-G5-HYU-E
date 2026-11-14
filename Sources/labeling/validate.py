"""Validate HYU label JSONL files against the schema and frozen snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from app.rag.applicability import VOCABULARY
from labeling._snapshot import DEFAULT_SNAPSHOT_ID, load_snapshot_rows

ANSWERABILITY = (
    "answerable",
    "partial",
    "unanswerable",
    "external_only",
    "korean_only",
    "unanswerable_unreadable",
)
BEHAVIORS = ("answer", "conditional_answer", "clarify", "abstain")
SLICES = ("unconditional", "conditional", "temporal", "negative", "multi_session")
ORIGINS = ("human", "agent_draft_human_edited", "agent_edited", "agent_draft")  # agent_edited: A27
SCOPES = ("national", "campus")
ANNOTATOR = re.compile(r"^(?:codex:[^\s]+|claude-code:[^\s]+|human:[A-Za-z][A-Za-z0-9_-]*)$")
# Who may adjudicate or verify (A33): a human's initials (short, not a model name) or an agent with its model id.
HUMAN_ID = re.compile(r"^human:[A-Za-z][A-Za-z0-9_-]{0,7}$")
AGENT_ID = re.compile(r"^claude-code:claude-[a-z]+-\d+(?:-\d+)*$")
MODEL_WORDS = re.compile(r"claude|codex|gpt|sonnet|opus|haiku|fable|gemini|llama|qwen", re.I)


def reviewer_ok(name: object, annotator: object = None) -> bool:
    """A valid adjudicator/verifier id that is not the case's own primary annotator (A33)."""
    if not isinstance(name, str) or name == annotator:
        return False
    return bool(AGENT_ID.fullmatch(name) or (HUMAN_ID.fullmatch(name) and not MODEL_WORDS.search(name)))


UPDATE_WORD = re.compile(r"\b(?:now|actually|changed?|updated?|instead|no longer|transferred?|switched?|moved?)\b", re.I)

REQUIRED_TYPES: dict[str, type] = {
    "case_id": str,
    "case_version": str,
    "snapshot_id": str,
    "slice": str,
    "origin": str,
    "annotator": str,
    "session_history": list,
    "question": str,
    "stated_profile": dict,
    "gold_profile": dict,
    "branch_attributes": list,
    "answerability": str,
    "expected_behavior": str,
    "acceptable_behaviors": list,
    "required_facts": list,
    "gold_evidence": list,
    "inapplicable_evidence": list,
    "outdated_evidence": list,
    "condition_scope": str,
    "reference_answer": str,
    "notes": str,
}


def _message(case_id: object, field: str, message: str) -> str:
    return f"{case_id if isinstance(case_id, str) and case_id else '<unknown>'}: {field}: {message}"


def _is_exact_type(value: object, expected: type) -> bool:
    return type(value) is expected


def _validate_profile(case_id: object, field: str, profile: object, errors: list[str]) -> None:
    if not isinstance(profile, dict):
        return
    for attribute, value in profile.items():
        if attribute not in VOCABULARY:
            errors.append(_message(case_id, field, f"unknown vocabulary attribute {attribute!r}"))
        elif not isinstance(value, str) or value not in VOCABULARY[attribute]:
            errors.append(_message(case_id, field, f"{attribute} value {value!r} is outside the vocabulary"))


def _has_stated_update(case: dict) -> bool:
    if case.get("slice") != "multi_session":
        return False
    texts = [turn.get("text", "") for turn in case.get("session_history", []) if isinstance(turn, dict)]
    texts.append(case.get("question", "") if isinstance(case.get("question"), str) else "")
    return any(UPDATE_WORD.search(text) for text in texts)


def _linked_family(row: dict, documents: dict[str, dict]) -> bool:
    family = row.get("version_family_id")
    return any(
        other.get("superseded_by")
        and (other.get("version_family_id") == family if family else other.get("superseded_by") == row["doc_id"])
        for other in documents.values()
    )


def _validate_evidence(
    case_id: object,
    field: str,
    entries: object,
    documents: dict[str, dict],
    errors: list[str],
) -> None:
    if not isinstance(entries, list):
        return
    for index, entry in enumerate(entries):
        name = f"{field}[{index}]"
        if not isinstance(entry, dict):
            errors.append(_message(case_id, name, "must be an object"))
            continue
        doc_id = entry.get("doc_id")
        if not isinstance(doc_id, str) or doc_id not in documents:
            errors.append(_message(case_id, name, f"doc_id {doc_id!r} does not exist in the snapshot"))
            continue
        start, end = entry.get("char_start"), entry.get("char_end")
        if type(start) is not int or type(end) is not int:
            errors.append(_message(case_id, name, "char_start and char_end must be integers"))
        elif not 0 <= start < end <= len(documents[doc_id]["text"]):
            errors.append(_message(case_id, name, "span must satisfy 0 <= char_start < char_end <= len(text)"))

        if field == "gold_evidence" and entry.get("applies_to_gold_profile") is not True:
            errors.append(_message(case_id, name, "applies_to_gold_profile must be true"))
        branch = entry.get("branch")  # optional, GUIDELINES 11.5: the branch condition this gold span supports
        if field == "gold_evidence" and branch is not None and (
            not isinstance(branch, dict) or not branch
            or any(a not in VOCABULARY or v not in VOCABULARY[a] for a, v in branch.items())
        ):
            errors.append(_message(case_id, name, "branch must be a non-empty {attribute: value} object in the vocabulary"))
        if field == "inapplicable_evidence" and not isinstance(entry.get("why"), str):
            errors.append(_message(case_id, name, "why must be a non-empty string"))
        elif field == "inapplicable_evidence" and not entry["why"].strip():
            errors.append(_message(case_id, name, "why must be a non-empty string"))
        if field == "outdated_evidence":
            row = documents[doc_id]
            if _linked_family(row, documents) and not row.get("superseded_by"):
                errors.append(_message(case_id, name, "doc_id is the newest linked version of its family"))


# Annotator files (T15/T16) never carry slice or origin; the merge adds them from drafts/quota_view.jsonl (A26).
MERGE_FIELDS = ("slice", "origin")


def validate_cases(cases: list[dict], rows: list[dict], snapshot_id: str, annotation: bool = False) -> list[str]:
    errors: list[str] = []
    documents = {row["doc_id"]: row for row in rows}
    seen: set[str] = set()

    for case in cases:
        if not isinstance(case, dict):
            errors.append(_message(None, "row", "must be an object"))
            continue
        case_id = case.get("case_id")
        for field, expected_type in REQUIRED_TYPES.items():
            if annotation and field in MERGE_FIELDS:
                continue
            if field not in case:
                errors.append(_message(case_id, field, "is required"))
            elif not _is_exact_type(case[field], expected_type):
                errors.append(_message(case_id, field, f"must be {expected_type.__name__}"))

        if isinstance(case_id, str):
            if case_id in seen:
                errors.append(_message(case_id, "case_id", "must be unique"))
            seen.add(case_id)
        if "split" in case and case["split"] not in ("dev", "test", "test2"):
            errors.append(_message(case_id, "split", "must be dev, test or test2"))
        if case.get("snapshot_id") != snapshot_id:
            errors.append(_message(case_id, "snapshot_id", f"must equal {snapshot_id}"))
        if not annotation and case.get("slice") not in SLICES:
            errors.append(_message(case_id, "slice", f"must be one of {sorted(SLICES)}"))
        if not annotation and case.get("origin") not in ORIGINS:
            errors.append(_message(case_id, "origin", f"must be one of {sorted(ORIGINS)}"))
        if not isinstance(case.get("annotator"), str) or not ANNOTATOR.fullmatch(case["annotator"]):
            errors.append(_message(case_id, "annotator", "must match codex:<model>, claude-code:<model>, or human:<initials>"))
        for field in ("adjudicated_by", "verified_by"):
            if field in case and not reviewer_ok(case[field], case.get("annotator")):
                errors.append(_message(case_id, field, "must be human:<initials> or claude-code:<model>, not the primary annotator (A33)"))

        history = case.get("session_history")
        if isinstance(history, list):
            for index, turn in enumerate(history):
                if not isinstance(turn, dict) or type(turn.get("role")) is not str or type(turn.get("text")) is not str:
                    errors.append(_message(case_id, f"session_history[{index}]", "must contain string role and text"))

        stated, gold = case.get("stated_profile"), case.get("gold_profile")
        _validate_profile(case_id, "stated_profile", stated, errors)
        _validate_profile(case_id, "gold_profile", gold, errors)
        if isinstance(stated, dict) and isinstance(gold, dict) and not _has_stated_update(case):
            for attribute in stated.keys() & gold.keys():
                if stated[attribute] != gold[attribute]:
                    errors.append(_message(case_id, "stated_profile", f"{attribute} must agree with gold_profile"))

        if "stale_update" in case and type(case["stale_update"]) is not bool:  # GUIDELINES 11.7
            errors.append(_message(case_id, "stale_update", "must be true or false"))
        branch_attributes = case.get("branch_attributes")
        if isinstance(branch_attributes, list):
            for attribute in branch_attributes:
                if not isinstance(attribute, str) or attribute not in VOCABULARY:
                    errors.append(_message(case_id, "branch_attributes", f"unknown vocabulary attribute {attribute!r}"))
        condition_sets = case.get("condition_sets")  # optional, vocabulary v1 (A17): alternatives joined by "or"
        if condition_sets is not None:
            if not isinstance(condition_sets, list) or len(condition_sets) < 2:
                errors.append(_message(case_id, "condition_sets", "must be a list of at least two alternative sets"))
            else:
                for group in condition_sets:
                    if not isinstance(group, dict) or not group:
                        errors.append(_message(case_id, "condition_sets", "each set must be a non-empty object"))
                        continue
                    for attribute, values in group.items():
                        if attribute not in VOCABULARY or not isinstance(values, list) or any(v not in VOCABULARY[attribute] for v in values):
                            errors.append(_message(case_id, "condition_sets", f"{attribute}={values!r} is outside the vocabulary"))
        if case.get("answerability") not in ANSWERABILITY:
            errors.append(_message(case_id, "answerability", f"must be one of {sorted(ANSWERABILITY)}"))
        behavior = case.get("expected_behavior")
        if behavior not in BEHAVIORS:
            errors.append(_message(case_id, "expected_behavior", f"must be one of {sorted(BEHAVIORS)}"))
        acceptable = case.get("acceptable_behaviors")
        if isinstance(acceptable, list):
            invalid = [value for value in acceptable if not isinstance(value, str) or value not in BEHAVIORS]
            if invalid:
                errors.append(_message(case_id, "acceptable_behaviors", f"contains invalid values {invalid}"))
            if behavior not in acceptable:
                errors.append(_message(case_id, "acceptable_behaviors", "must include expected_behavior"))

        for field in ("required_facts", "acceptable_behaviors", "branch_attributes"):
            values = case.get(field)
            if isinstance(values, list) and any(type(value) is not str for value in values):
                errors.append(_message(case_id, field, "must contain only strings"))
        if case.get("condition_scope") not in SCOPES:
            errors.append(_message(case_id, "condition_scope", "must be national or campus"))

        for field in ("gold_evidence", "inapplicable_evidence", "outdated_evidence"):
            _validate_evidence(case_id, field, case.get(field), documents, errors)
        if behavior in ("answer", "conditional_answer") and not case.get("gold_evidence"):
            errors.append(_message(case_id, "gold_evidence", f"is required for {behavior}"))
        if behavior == "abstain" and case.get("answerability") == "answerable":
            errors.append(_message(case_id, "answerability", "answerable cases cannot abstain"))
        if behavior in ("conditional_answer", "clarify") and not branch_attributes:
            errors.append(_message(case_id, "branch_attributes", f"is required for {behavior}"))
    return errors


def load_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def validate_file(path: Path, snapshot_id: str = DEFAULT_SNAPSHOT_ID, annotation: bool = False) -> list[str]:
    return validate_cases(load_cases(path), load_snapshot_rows(snapshot_id), snapshot_id, annotation)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT_ID)
    parser.add_argument("--annotation", action="store_true", help="annotator file: slice and origin are added at merge")
    args = parser.parse_args(argv)
    try:
        errors = validate_file(args.file, args.snapshot, args.annotation)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
