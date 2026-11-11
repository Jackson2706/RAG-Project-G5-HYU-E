"""Human review of the T14 question drafts (PLAYBOOK A26).

    python -m labeling.review make    # drafts -> drafts/review.csv + drafts/hints.jsonl (refuses to overwrite)
    python -m labeling.review apply --initials JK   # review.csv -> questions.jsonl (+ quota view), prints the report

review.csv columns: id, slice, campus, persona, session_history, question, decision, edited_question, notes.
- decision: keep | edit | agent_edit | delete. `edit` (a human edit) and `agent_edit` (an edit by Claude Code,
  origin agent_edited, A27) use edited_question and the session_history cell as left.
- A new question of your own: a row with an empty id and decision `new` (fill slice, campus, persona,
  question; session_history only for multi_session). Separate history turns with " || ".

Annotators (T15, T16) get only `questions.jsonl`: case_id, persona_id, session_history, question. The hints
(slice, intended attributes/answerability, why, topic doc ids) stay in drafts/hints.jsonl and
drafts/quota_view.jsonl, for quotas and the human review only.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from labeling.drafts import CAMPUSES, SLICES, validate_drafts

LABELS = Path("data/HYU/labels")
DRAFTS = LABELS / "drafts"
COLUMNS = ["id", "slice", "campus", "persona", "session_history", "question", "decision", "edited_question", "notes"]
HINT_FIELDS = ("draft_id", "slice", "campus", "topic_doc_ids", "intended_attributes", "intended_answerability", "why")
SEP = " || "
AGENT_EDITOR = "claude-code:claude-opus-5-5"
HUMAN_SHARE_TARGET = 0.0  # A28: no human questions (A27 had 0.10, A26 0.30); the share is reported, not gated
# GUIDELINES.md section 7: final targets per slice x campus (180 cases)
TARGETS = {("unconditional", "seoul"): 38, ("unconditional", "erica"): 25, ("conditional", "seoul"): 25,
           ("conditional", "erica"): 20, ("temporal", "seoul"): 13, ("temporal", "erica"): 5,
           ("negative", "seoul"): 22, ("negative", "erica"): 14, ("multi_session", "seoul"): 10,
           ("multi_session", "erica"): 8}  # fmt: skip


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def make(labels: Path = LABELS, force: bool = False) -> int:
    drafts_dir = labels / "drafts"
    sheet = drafts_dir / "review.csv"
    if sheet.exists() and not force:
        raise SystemExit(f"{sheet} exists (it may hold your decisions); pass --force to overwrite")
    drafts = _jsonl(drafts_dir / "questions_codex.jsonl")
    _write_jsonl(drafts_dir / "hints.jsonl", [{k: row[k] for k in HINT_FIELDS} for row in drafts])
    with open(sheet, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, COLUMNS)
        writer.writeheader()
        for row in drafts:
            writer.writerow({"id": row["draft_id"], "slice": row["slice"], "campus": row["campus"],
                             "persona": row["persona_id"], "session_history": SEP.join(row["session_history"]),
                             "question": row["question"], "decision": "", "edited_question": "", "notes": ""})  # fmt: skip
    return len(drafts)


def apply(labels: Path = LABELS, initials: str = "") -> dict:
    """Apply review.csv. Returns the report; raises SystemExit on any row error (nothing is written then)."""
    drafts_dir = labels / "drafts"
    drafts = {row["draft_id"]: row for row in _jsonl(drafts_dir / "questions_codex.jsonl")}
    personas = {p["persona_id"]: p["gold_profile"]["campus"] for p in json.loads((labels / "personas.json").read_text())}
    with open(drafts_dir / "review.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    errors, final, seen, new_count = [], [], set(), 0
    for line, row in enumerate(rows, 2):
        decision = (row.get("decision") or "").strip().lower()
        draft_id = (row.get("id") or "").strip()
        history = [t.strip() for t in (row.get("session_history") or "").split(SEP.strip()) if t.strip()]
        if decision == "delete":
            seen.add(draft_id)
            continue
        if decision == "new":
            new_count += 1
            case = {"case_id": f"H-{new_count:03d}", "slice": row.get("slice", "").strip(), "campus": row.get("campus", "").strip(),
                    "persona_id": row.get("persona", "").strip(), "session_history": history,
                    "question": (row.get("question") or "").strip(), "origin": "human", "drafted_by": f"human:{initials}", "edited_by": None}  # fmt: skip
        elif decision in ("keep", "edit", "agent_edit") and draft_id in drafts:
            seen.add(draft_id)
            draft = drafts[draft_id]
            edited = decision in ("edit", "agent_edit")
            origin = {"keep": "agent_draft", "edit": "agent_draft_human_edited", "agent_edit": "agent_edited"}[decision]
            editor = {"edit": f"human:{initials}", "agent_edit": AGENT_EDITOR}.get(decision)
            question = (row.get("edited_question") or "").strip() if edited else draft["question"]
            if edited and not question:
                errors.append(f"line {line}: decision edit needs edited_question")
            changed_history = history != draft["session_history"]
            case = {"case_id": draft_id, "slice": draft["slice"], "campus": draft["campus"], "persona_id": draft["persona_id"],
                    "session_history": history if edited else draft["session_history"], "question": question,
                    "origin": origin, "drafted_by": draft["annotator"], "edited_by": editor}  # fmt: skip
            if changed_history and not edited:
                errors.append(f"line {line}: session_history changed but decision is keep (use edit)")
        else:
            errors.append(f"line {line}: decision must be keep/edit/delete for a draft id, or new with an empty id (got {decision!r}, id {draft_id!r})")
            continue
        if case["slice"] not in SLICES or case["campus"] not in CAMPUSES:
            errors.append(f"line {line}: bad slice/campus {case['slice']!r}/{case['campus']!r}")
        elif personas.get(case["persona_id"]) != case["campus"]:
            errors.append(f"line {line}: persona {case['persona_id']!r} is not a {case['campus']} persona")
        if not case["question"]:
            errors.append(f"line {line}: empty question")
        if (case["slice"] == "multi_session") != bool(case["session_history"]):
            errors.append(f"line {line}: session_history is required for multi_session and only there")
        final.append(case)
    missing = sorted(set(drafts) - seen)
    if missing:
        errors.append(f"{len(missing)} drafts have no decision row: {', '.join(missing[:5])}…")
    if any(c["origin"] in ("human", "agent_draft_human_edited") for c in final) and not initials:
        errors.append("--initials is required when you edit or add questions")
    if errors:
        raise SystemExit("review.csv errors (nothing written):\n  " + "\n  ".join(errors))

    _write_jsonl(labels / "questions.jsonl",  # the annotator view: no slice, no hints
                 [{k: c[k] for k in ("case_id", "persona_id", "session_history", "question")} for c in final])
    _write_jsonl(drafts_dir / "quota_view.jsonl",
                 [{k: c[k] for k in ("case_id", "slice", "campus", "persona_id", "origin", "drafted_by", "edited_by")} for c in final])
    origins = Counter(c["origin"] for c in final)
    human = origins["human"] + origins["agent_draft_human_edited"]
    return {"cases": len(final), "origins": dict(origins), "human_share": human / len(final) if final else 0.0,
            "slice_campus": {f"{s}/{c}": f"{n}/{TARGETS[(s, c)]}" for (s, c), n in
                             sorted(Counter((c["slice"], c["campus"]) for c in final).items())},
            "per_persona": dict(sorted(Counter(c["persona_id"] for c in final).items()))}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("make").add_argument("--force", action="store_true")
    sub.add_parser("apply").add_argument("--initials", default="")
    args = parser.parse_args(argv)
    if args.command == "make":
        print(f"Wrote {make(force=args.force)} rows to {DRAFTS / 'review.csv'} and hints to {DRAFTS / 'hints.jsonl'}")
        return 0
    _, draft_errors = validate_drafts(DRAFTS / "questions_codex.jsonl", LABELS / "topics.jsonl", LABELS / "personas.json")
    if draft_errors:  # labeling.drafts check on the source drafts
        raise SystemExit("labeling.drafts check failed on questions_codex.jsonl:\n  " + "\n  ".join(draft_errors))
    report = apply(initials=args.initials)
    print(json.dumps(report, indent=2))
    share = report["human_share"]
    print(f"Human share {share:.1%}" + (" (the set is 100% agent-written, A28)" if share == 0 else "") + "; "
          f"{report['cases']} cases (target 180). Annotators get only {LABELS / 'questions.jsonl'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
