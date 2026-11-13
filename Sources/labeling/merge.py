"""G4 label pipeline (PLAYBOOK A31/A32): merge → verification sheets → apply verification → labeling.freeze.

Run from Sources/:
  python -m labeling.merge merge  --sheet <adjudication_sheet.csv> [--accept-rest human:XX] --out data/HYU/labels/merged.jsonl
  python -m labeling.merge sheets data/HYU/labels/merged.jsonl --out data/HYU/labels/verification
  python -m labeling.merge verify data/HYU/labels/merged.jsonl --sheets data/HYU/labels/verification --out data/HYU/labels/all.jsonl
  python -m labeling.freeze data/HYU/labels/all.jsonl --out data/HYU/labels --dev-size 50

Primary labels: Codex batches 01-03 and Sonnet batches 04-06. Every value on the adjudication sheet is the
adjudicator's: a filled final_* column, or the proposed_* values when accept_proposal is "yes". A row changed on
the sheet gets origin agent_draft_human_edited when a human adjudicated it, agent_edited when an agent did (A33).
final_answerability = EXCLUDE (adjudication) or fix_answerability = EXCLUDE / no verifier (verification) marks a
case `exclude: <reason>`; labeling.freeze drops those after splitting and lists them in excluded.jsonl.
A33 (autonomous mode): the adjudicator and verifier may be agents (claude-code:<model>), and every test case plus
every labeling.checks violation is verified (`--violations`).
Spreadsheet CSVs are read with utf-8-sig (Excel adds a BOM); blank rows are skipped.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

from app.config import DATA_DIR

from labeling._snapshot import DEFAULT_SNAPSHOT_ID, load_snapshot_rows
from labeling.freeze import split
from labeling.validate import AGENT_ID, reviewer_ok, validate_cases

EXCLUDE = "EXCLUDE"

LABELS = DATA_DIR / "HYU" / "labels"  # not cwd-relative: a cwd-relative path made Sources/Sources/ (A33)
PRIMARY = ("annot_codex/batch_0[1-3].jsonl", "annot_sonnet/batch_0[4-6].jsonl")
FIELDS = ("answerability", "expected_behavior", "acceptable_behaviors", "branch_attributes")
LISTS = ("acceptable_behaviors", "branch_attributes")
DEV_SIZE, SEED = 50, 13  # must match the labeling.freeze call in the docstring; every command prints them
# Verification files (A32): order conditional, temporal, negative, multi_session, then the unconditional spot check.
SHEETS = {"1_conditional.csv": ("conditional",), "2_temporal_negative.csv": ("temporal", "negative"),
          "3_multi_session_spot.csv": ("multi_session", "unconditional")}  # fmt: skip
SPOT_SHARE = 1.0  # A33: every test case is verified (A31 had a 0.2 spot check of unconditional cases)
VERIFY_COLS = ("case_id", "split", "slice", "question", "stated_profile", "answerability", "expected_behavior",
               "acceptable_behaviors", "branch_attributes", "required_facts", "gold_evidence", "evidence_supports_facts",
               "fix_answerability", "fix_expected_behavior", "fix_acceptable_behaviors", "fix_branch_attributes", "fix_note",
               "check_violations", "verifier")  # fmt: skip


def _jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _human(initials: str) -> str:
    initials = initials.strip()
    value = initials if initials.startswith("human:") else f"human:{initials}"
    if not reviewer_ok(value):
        raise ValueError(f"{initials!r} is not a human's initials (expected e.g. JD or human:JD)")
    return value


def _who(name: str, case: dict | None = None) -> str:
    """A human's initials, or an agent id such as claude-code:claude-opus-5-5 (A33); never the case's own annotator."""
    name = name.strip()
    who = name if AGENT_ID.fullmatch(name) else _human(name)
    if case is not None and who == case.get("annotator"):
        raise ValueError(f"{case['case_id']}: {who} is the primary annotator and cannot adjudicate or verify its own label")
    return who


def _origin(who: str) -> str:
    return "agent_draft_human_edited" if who.startswith("human:") else "agent_edited"


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
                case["adjudicated_by"] = _who(accept_rest, case)
            cases.append(case)
            continue
        accepted = _choice(decision, "accept_proposal") == "yes"
        changed = False
        if decision.get("final_answerability", "").strip() == EXCLUDE:
            if not decision.get("adjudicator", "").strip():
                raise ValueError(f"{row['case_id']}: EXCLUDE needs an adjudicator")
            case["adjudicated_by"] = _who(decision["adjudicator"], case)
            case["exclude"] = f"adjudication: {decision.get('final_evidence_note', '').strip() or 'no reason given'}"
            cases.append(case)
            continue
        for field in FIELDS:
            cell = decision.get(f"final_{field}", "").strip() or (decision.get(f"proposed_{field}", "").strip() if accepted else "")
            if cell and _value(field, cell) != case[field]:
                case[field], changed = _value(field, cell), True
        if decision.get("final_evidence_note", "").strip():
            case["notes"] = f"{case['notes']} [adjudication] {decision['final_evidence_note'].strip()}".strip()
        if decision.get("adjudicator", "").strip():
            case["adjudicated_by"] = _who(decision["adjudicator"], case)
            if changed:
                case["origin"] = _origin(case["adjudicated_by"])
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


def selected_test_cases(cases: list[dict], extra: dict[str, list[str]] | None = None) -> list[dict]:
    """Cases to verify: every non-unconditional test case, a SPOT_SHARE share of the unconditional ones (A33: all), and every
    case in `extra` (labeling.checks violations, dev or test; A33). Excluded cases are not verified again.

    The split runs over all cases, excluded ones too, so an exclusion never moves another case between dev and test.
    A31 also asks for every test case of batches 04-06; those batches hold only conditional, temporal, negative
    and multi_session cases, so they are all in the full check and the spot pool is exactly the other cases.
    """
    extra = extra or {}
    _, test = split(cases, DEV_SIZE, SEED)
    unconditional = sorted(c["case_id"] for c in test if c["slice"] == "unconditional")
    spot = set(random.Random(SEED).sample(unconditional, round(SPOT_SHARE * len(unconditional))))
    test_ids = {c["case_id"] for c in test}
    chosen = [c for c in cases if "exclude" not in c and (
        (c["case_id"] in test_ids and (c["slice"] != "unconditional" or c["case_id"] in spot)) or c["case_id"] in extra)]
    order = ("conditional", "temporal", "negative", "multi_session", "unconditional")
    return sorted(chosen, key=lambda c: (order.index(c["slice"]), c["case_id"]))


def verification_rows(cases: list[dict], documents: dict[str, dict], extra: dict[str, list[str]] | None = None) -> dict[str, list[dict]]:
    extra = extra or {}
    _, test = split(cases, DEV_SIZE, SEED)
    test_ids = {c["case_id"] for c in test}
    sheets: dict[str, list[dict]] = {name: [] for name in SHEETS}
    for case in selected_test_cases(cases, extra):
        name = next(n for n, slices in SHEETS.items() if case["slice"] in slices)
        sheets[name].append({
            "case_id": case["case_id"], "split": "test" if case["case_id"] in test_ids else "dev", "slice": case["slice"],
            "question": case["question"], "check_violations": "\n".join(extra.get(case["case_id"], [])),
            "stated_profile": json.dumps(case["stated_profile"]), "answerability": case["answerability"],
            "expected_behavior": case["expected_behavior"], "acceptable_behaviors": json.dumps(case["acceptable_behaviors"]),
            "branch_attributes": json.dumps(case["branch_attributes"]),
            "required_facts": "\n".join(case["required_facts"]), "gold_evidence": _evidence(case["gold_evidence"], documents),
        })  # fmt: skip
    return sheets


def apply_verification(cases: list[dict], sheet_rows: list[dict], extra: dict[str, list[str]] | None = None,
                       exclude_unverified: bool = False) -> tuple[list[dict], list[str]]:
    """Fixes and verifier names from the filled sheets. Returns (cases, selected ids still unverified).

    A selected id missing from the sheets (a deleted row) counts as unverified, never as silently dropped.
    exclude_unverified (A33: unresolved -> EXCLUDE) marks every unverified case `exclude`.
    fix_answerability = EXCLUDE marks the case `exclude` with the fix_note as the reason.
    """
    by_id = {c["case_id"]: dict(c) for c in cases}
    expected = {c["case_id"] for c in selected_test_cases(cases, extra)}
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
        who = _who(row["verifier"], case)
        edited = _origin(who)
        fix = row.get("fix_answerability", "").strip()
        if fix == EXCLUDE:
            case["exclude"], case["verified_by"] = f"verification: {row.get('fix_note', '').strip() or 'no reason given'}", who
            continue
        if fix and fix != case["answerability"]:
            case["answerability"], case["origin"] = fix, edited
        fix = row.get("fix_expected_behavior", "").strip()
        if fix and fix != case["expected_behavior"]:
            old = case["expected_behavior"]  # the old behaviour stops being acceptable unless the human lists it again
            case["acceptable_behaviors"] = [fix, *(b for b in case["acceptable_behaviors"] if b not in (fix, old))]
            case["expected_behavior"], case["origin"] = fix, edited
        for field in ("acceptable_behaviors", "branch_attributes"):
            cell = row.get(f"fix_{field}", "").strip()
            if cell and _value(field, cell) != case[field]:
                case[field], case["origin"] = _value(field, cell), edited
        supports = _choice(row, "evidence_supports_facts")
        if supports:
            case["evidence_supports_facts"] = supports == "yes"
        if row.get("fix_note", "").strip():
            case["notes"] = f"{case['notes']} [verification] {row['fix_note'].strip()}".strip()
        case["verified_by"] = who
    unverified = sorted(unverified + sorted(expected - seen))
    if exclude_unverified:
        for case_id in unverified:
            by_id[case_id]["exclude"] = "verification: unresolved (not verified)"
    return [by_id[k] for k in sorted(by_id)], unverified


def _write_jsonl(path: Path, cases: list[dict]) -> None:
    path.write_text("".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in cases), encoding="utf-8")


def _violations(path: Path | None) -> dict[str, list[str]]:
    """labeling.checks output (one {case_id, check, detail} per line) -> {case_id: ["check: detail", ...]}."""
    out: dict[str, list[str]] = {}
    for v in _jsonl(path) if path else []:
        out.setdefault(v["case_id"], []).append(f"{v['check']}: {v['detail']}")
    return out


def _sha(path: Path | None) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path else "none"


def _check(cases: list[dict]) -> None:
    cases = [c for c in cases if "exclude" not in c]  # an excluded label may stay invalid; it never reaches a split
    errors = validate_cases(cases, load_snapshot_rows(DEFAULT_SNAPSHOT_ID), DEFAULT_SNAPSHOT_ID)
    if errors:
        raise ValueError("merged labels do not validate:\n" + "\n".join(errors[:20]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--sheet", type=Path, required=True)
    m.add_argument("--accept-rest", help="human:<initials> or claude-code:<model> (A33): accepts the primary labels of every row not on the sheet")
    m.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("sheets")
    s.add_argument("merged", type=Path)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--violations", type=Path, help="labeling.checks output; those cases are verified too (A33)")
    v = sub.add_parser("verify")
    v.add_argument("merged", type=Path)
    v.add_argument("--sheets", type=Path, required=True)
    v.add_argument("--out", type=Path, required=True)
    v.add_argument("--violations", type=Path, help="the same file given to `sheets`")
    v.add_argument("--exclude-unverified", action="store_true", help="A33: an unverified selected case is excluded")
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
        sheets = verification_rows(merged, documents, _violations(args.violations))
        for path in targets:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=VERIFY_COLS)
                writer.writeheader()
                writer.writerows(sheets[path.name])
        (args.out / "VIOLATIONS.sha256").write_text(_sha(args.violations) + "\n", encoding="utf-8")
        print(json.dumps({**{name: len(rows) for name, rows in sheets.items()}, "dev_size": DEV_SIZE, "seed": SEED}, indent=2))
    else:
        written = (args.sheets / "VIOLATIONS.sha256").read_text(encoding="utf-8").strip()
        if written != _sha(args.violations):
            raise ValueError("--violations differs from the file the sheets were built with (pass the same file to both)")
        rows = []
        for name in SHEETS:
            rows += read_csv(args.sheets / name)
        cases, unverified = apply_verification(_jsonl(args.merged), rows, _violations(args.violations), args.exclude_unverified)
        _check(cases)
        _write_jsonl(args.out, cases)
        note = "# Test items not verified by the deadline (limitation, A32)\n\n" + "".join(f"- {c}\n" for c in unverified)
        (args.sheets / "UNVERIFIED.md").write_text(note if unverified else "# All selected test items were verified.\n", encoding="utf-8")
        print(json.dumps({"cases": len(cases), "verified": sum("verified_by" in c for c in cases), "unverified": unverified,
                          "excluded": sum("exclude" in c for c in cases),
                          "freeze_with": {"dev_size": DEV_SIZE, "seed": SEED}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
