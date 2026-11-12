"""G4 label pipeline (PLAYBOOK A31/A32): merge → verification sheets → apply verification → labeling.freeze.

Run from Sources/:
  python -m labeling.merge merge  --sheet <adjudication_sheet.csv> [--accept-rest human:XX] --out data/HYU/labels/merged.jsonl
  python -m labeling.merge sheets data/HYU/labels/merged.jsonl --out data/HYU/labels/verification
  python -m labeling.merge verify data/HYU/labels/merged.jsonl --sheets data/HYU/labels/verification --out data/HYU/labels/all.jsonl
  python -m labeling.freeze data/HYU/labels/all.jsonl --out data/HYU/labels --dev-size 50

Primary labels: Codex batches 01-03 and Sonnet batches 04-06. Every value on the adjudication sheet is the
human's: a filled final_* column, or the proposed_* values when accept_proposal is "yes". A row changed on the
sheet (also by an accepted Claude Code proposal) gets origin agent_draft_human_edited: the human chose the value.
Spreadsheet CSVs are read with utf-8-sig (Excel adds a BOM); blank rows are skipped.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

from labeling._snapshot import DEFAULT_SNAPSHOT_ID, load_snapshot_rows
from labeling.freeze import split
from labeling.validate import validate_cases

HUMAN = re.compile(r"^human:[A-Za-z][A-Za-z0-9_-]*$")

LABELS = Path("data/HYU/labels")
PRIMARY = ("annot_codex/batch_0[1-3].jsonl", "annot_sonnet/batch_0[4-6].jsonl")
FIELDS = ("answerability", "expected_behavior", "acceptable_behaviors", "branch_attributes")
LISTS = ("acceptable_behaviors", "branch_attributes")
DEV_SIZE, SEED = 50, 13  # must match the labeling.freeze call in the docstring; every command prints them
# Verification files (A32): order conditional, temporal, negative, multi_session, then the unconditional spot check.
SHEETS = {"1_conditional.csv": ("conditional",), "2_temporal_negative.csv": ("temporal", "negative"),
          "3_multi_session_spot.csv": ("multi_session", "unconditional")}  # fmt: skip
SPOT_SHARE = 0.2
VERIFY_COLS = ("case_id", "split", "slice", "question", "stated_profile", "answerability", "expected_behavior",
               "acceptable_behaviors", "branch_attributes", "required_facts", "gold_evidence", "evidence_supports_facts",
               "fix_answerability", "fix_expected_behavior", "fix_acceptable_behaviors", "fix_branch_attributes", "fix_note",
               "verifier")  # fmt: skip


def _jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _human(initials: str) -> str:
    initials = initials.strip()
    value = initials if initials.startswith("human:") else f"human:{initials}"
    if not HUMAN.fullmatch(value) or value.lower() in ("human:codex", "human:claude", "human:sonnet", "human:opus"):
        raise ValueError(f"{initials!r} is not a human's initials (expected e.g. JD or human:JD)")
    return value


def _choice(row: dict, column: str) -> str:
    """A yes/no cell; anything else is an error, so a typo never silently drops the human's decision."""
    value = (row.get(column) or "").strip().lower()
    if value not in ("", "yes", "no"):
        raise ValueError(f"{row['case_id']}: {column} must be yes, no or empty, not {value!r}")
    return value


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(handle, restval="")]
    return [r for r in rows if r.get("case_id")]


def _value(field: str, text: str):
    """A sheet cell: JSON lists or comma-separated values for list fields, plain text otherwise."""
    text = text.strip()
    if field not in LISTS:
        return text
    return json.loads(text) if text.startswith("[") else [v.strip() for v in text.split(",") if v.strip()]


def primary_labels(labels: Path = LABELS) -> list[dict]:
    rows = [row for pattern in PRIMARY for path in sorted(labels.glob(pattern)) for row in _jsonl(path)]
    rows = [row for row in rows if "expected_behavior" in row]
    if len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate case_id across the primary label files")
    return rows


def merge(rows: list[dict], quota: dict[str, dict], sheet: list[dict], accept_rest: str | None = None) -> tuple[list[dict], list[str]]:
    """Primary labels + slice/origin + the human's sheet values. Returns (cases, sheet rows still pending)."""
    decisions = {r["case_id"]: r for r in sheet if r.get("case_id", "").strip()}
    if len(decisions) != len(sheet):
        raise ValueError("a case_id appears twice on the adjudication sheet")
    unknown = sorted(set(decisions) - {r["case_id"] for r in rows})
    if unknown:
        raise ValueError(f"sheet rows without a primary label: {unknown}")
    cases, pending = [], []
    for row in rows:
        case = {**row, "slice": quota[row["case_id"]]["slice"], "origin": quota[row["case_id"]]["origin"]}
        decision = decisions.get(row["case_id"])
        if decision is None:
            if accept_rest:
                case["adjudicated_by"] = _human(accept_rest)
            cases.append(case)
            continue
        accepted = _choice(decision, "accept_proposal") == "yes"
        changed = False
        for field in FIELDS:
            cell = decision.get(f"final_{field}", "").strip() or (decision.get(f"proposed_{field}", "").strip() if accepted else "")
            if cell and _value(field, cell) != case[field]:
                case[field], changed = _value(field, cell), True
        if decision.get("final_evidence_note", "").strip():
            case["notes"] = f"{case['notes']} [adjudication] {decision['final_evidence_note'].strip()}".strip()
        if decision.get("adjudicator", "").strip():
            case["adjudicated_by"] = _human(decision["adjudicator"])
            if changed:
                case["origin"] = "agent_draft_human_edited"
        else:
            pending.append(row["case_id"])
        cases.append(case)
    return sorted(cases, key=lambda c: c["case_id"]), pending


def _evidence(spans: list[dict], documents: dict[str, dict], context: int = 120) -> str:
    """Each gold span inside its context, the span itself between ⟦ ⟧."""
    out = []
    for span in spans:
        doc = documents[span["doc_id"]]
        text, start, end = doc["text"], span["char_start"], span["char_end"]
        gold = text[start:end] if end - start <= 600 else f"{text[start:start + 300]} … {text[end - 300:end]}"
        shown = f"…{text[max(0, start - context):start]}⟦{gold}⟧{text[end:end + context]}…".replace("\n", " ")
        out.append(f"[{span['doc_id'][:8]} {doc.get('campus', '')} {(doc.get('post_date') or '')[:10]} {start}-{end}] {shown}")
    return "\n".join(out)


def selected_test_cases(cases: list[dict]) -> list[dict]:
    """Test items to verify (A31): every non-unconditional test case, then a 20% spot check of the rest.

    A31 also asks for every test case of batches 04-06; those batches hold only conditional, temporal, negative
    and multi_session cases, so they are all in the full check and the spot pool is exactly the other cases.
    """
    _, test = split(cases, DEV_SIZE, SEED)
    unconditional = sorted(c["case_id"] for c in test if c["slice"] == "unconditional")
    spot = set(random.Random(SEED).sample(unconditional, round(SPOT_SHARE * len(unconditional))))
    chosen = [c for c in test if c["slice"] != "unconditional" or c["case_id"] in spot]
    order = ("conditional", "temporal", "negative", "multi_session", "unconditional")
    return sorted(chosen, key=lambda c: (order.index(c["slice"]), c["case_id"]))


def verification_rows(cases: list[dict], documents: dict[str, dict]) -> dict[str, list[dict]]:
    chosen = selected_test_cases(cases)
    sheets: dict[str, list[dict]] = {name: [] for name in SHEETS}
    for case in chosen:
        name = next(n for n, slices in SHEETS.items() if case["slice"] in slices)
        sheets[name].append({
            "case_id": case["case_id"], "split": "test", "slice": case["slice"], "question": case["question"],
            "stated_profile": json.dumps(case["stated_profile"]), "answerability": case["answerability"],
            "expected_behavior": case["expected_behavior"], "acceptable_behaviors": json.dumps(case["acceptable_behaviors"]),
            "branch_attributes": json.dumps(case["branch_attributes"]),
            "required_facts": "\n".join(case["required_facts"]), "gold_evidence": _evidence(case["gold_evidence"], documents),
        })  # fmt: skip
    return sheets


def apply_verification(cases: list[dict], sheet_rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Fixes and verifier initials from the filled sheets. Returns (cases, selected test ids still unverified).

    A selected id missing from the sheets (a deleted row) counts as unverified, never as silently dropped.
    """
    by_id = {c["case_id"]: dict(c) for c in cases}
    expected = {c["case_id"] for c in selected_test_cases(cases)}
    seen: set[str] = set()
    unverified = []
    for row in sheet_rows:
        case_id = row["case_id"]
        if case_id not in expected:
            raise ValueError(f"{case_id} is on a verification sheet but was not selected from the test split (the split changed)")
        if case_id in seen:
            raise ValueError(f"{case_id} appears twice on the verification sheets")
        seen.add(case_id)
        if not row.get("verifier", "").strip():
            unverified.append(case_id)
            continue
        case = by_id[case_id]
        fix = row.get("fix_answerability", "").strip()
        if fix and fix != case["answerability"]:
            case["answerability"], case["origin"] = fix, "agent_draft_human_edited"
        fix = row.get("fix_expected_behavior", "").strip()
        if fix and fix != case["expected_behavior"]:
            old = case["expected_behavior"]  # the old behaviour stops being acceptable unless the human lists it again
            case["acceptable_behaviors"] = [fix, *(b for b in case["acceptable_behaviors"] if b not in (fix, old))]
            case["expected_behavior"], case["origin"] = fix, "agent_draft_human_edited"
        for field in ("acceptable_behaviors", "branch_attributes"):
            cell = row.get(f"fix_{field}", "").strip()
            if cell and _value(field, cell) != case[field]:
                case[field], case["origin"] = _value(field, cell), "agent_draft_human_edited"
        supports = _choice(row, "evidence_supports_facts")
        if supports:
            case["evidence_supports_facts"] = supports == "yes"
        if row.get("fix_note", "").strip():
            case["notes"] = f"{case['notes']} [verification] {row['fix_note'].strip()}".strip()
        case["verified_by"] = _human(row["verifier"])
    unverified += sorted(expected - seen)
    return [by_id[k] for k in sorted(by_id)], sorted(unverified)


def _write_jsonl(path: Path, cases: list[dict]) -> None:
    path.write_text("".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in cases), encoding="utf-8")


def _check(cases: list[dict]) -> None:
    errors = validate_cases(cases, load_snapshot_rows(DEFAULT_SNAPSHOT_ID), DEFAULT_SNAPSHOT_ID)
    if errors:
        raise ValueError("merged labels do not validate:\n" + "\n".join(errors[:20]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--sheet", type=Path, required=True)
    m.add_argument("--accept-rest", help="human:<initials>: the human accepts the primary labels of every row not on the sheet")
    m.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("sheets")
    s.add_argument("merged", type=Path)
    s.add_argument("--out", type=Path, required=True)
    v = sub.add_parser("verify")
    v.add_argument("merged", type=Path)
    v.add_argument("--sheets", type=Path, required=True)
    v.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "merge":
        quota = {r["case_id"]: r for r in _jsonl(LABELS / "drafts" / "quota_view.jsonl")}
        sheet = read_csv(args.sheet)
        cases, pending = merge(primary_labels(), quota, sheet, args.accept_rest)
        _check(cases)
        _write_jsonl(args.out, cases)
        print(json.dumps({"cases": len(cases), "sheet_rows": len(sheet), "pending_sheet_rows": pending,
                          "not_adjudicated": sum("adjudicated_by" not in c for c in cases)}, indent=2))  # fmt: skip
    elif args.command == "sheets":
        documents = {row["doc_id"]: row for row in load_snapshot_rows(DEFAULT_SNAPSHOT_ID)}
        args.out.mkdir(parents=True, exist_ok=True)
        targets = [args.out / name for name in SHEETS]
        if any(path.exists() for path in targets):
            raise FileExistsError(f"refusing to overwrite verification sheets in {args.out} (they may hold the human's work)")
        merged = _jsonl(args.merged)
        pending = [c["case_id"] for c in merged if "adjudicated_by" not in c]
        if pending:
            raise ValueError(f"adjudicate first: {len(pending)} cases have no adjudicated_by (e.g. {pending[:5]})")
        sheets = verification_rows(merged, documents)
        for path in targets:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=VERIFY_COLS)
                writer.writeheader()
                writer.writerows(sheets[path.name])
        print(json.dumps({**{name: len(rows) for name, rows in sheets.items()}, "dev_size": DEV_SIZE, "seed": SEED}, indent=2))
    else:
        rows = []
        for name in SHEETS:
            rows += read_csv(args.sheets / name)
        cases, unverified = apply_verification(_jsonl(args.merged), rows)
        _check(cases)
        _write_jsonl(args.out, cases)
        note = "# Test items not verified by the deadline (limitation, A32)\n\n" + "".join(f"- {c}\n" for c in unverified)
        (args.sheets / "UNVERIFIED.md").write_text(note if unverified else "# All selected test items were verified.\n", encoding="utf-8")
        print(json.dumps({"cases": len(cases), "verified": sum("verified_by" in c for c in cases), "unverified": unverified,
                          "freeze_with": {"dev_size": DEV_SIZE, "seed": SEED}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
