"""Deck v3 Part 1a/1b (post-hoc, saved test-1 outputs only): the 15 student-dependent cases and wrong-group replies.

Run from Sources/:  python scripts/deck_v3_part1.py
-> Report/slides/deck_v3/part1a_branching_cases.csv, part1b_wrong_group.json

Reply types: evaluator v2 (hyu_test_v2_per_case.csv). Content: evaluator v3 judgments (quality_v3/raw), which exist only
for B0, R15, R16, A0, G0, G1. Labels are read with the runner's reader. Nothing is re-run.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402

from app.config import REPORT_DIR, RESULTS_DIR  # noqa: E402

OUT = REPORT_DIR / "slides" / "deck_v3"
ALL = ("B0", "R5", "R9S", "R15", "R16", "G0", "G1", "A0", "A1", "A2", "A3", "A4", "A6")
JUDGED = ("B0", "R15", "R16", "A0", "G0", "G1")
ANSWERED = ("answer", "conditional_answer")


def load_v3():
    raw = RESULTS_DIR / "quality_v3" / "raw"
    key = {k["id"]: k for k in map(json.loads, open(raw / "key.jsonl"))}
    items = {i["id"]: i for i in map(json.loads, open(raw / "items_test.jsonl"))}
    judged = {j["id"]: j for f in sorted((raw / "judgments").glob("test_*.jsonl")) for j in map(json.loads, open(f))}
    return {(key[i]["preset"].split("_")[0], key[i]["case_id"]): {**judged[i], "type": items[i]["reply_type"], "reply": items[i]["reply"]} for i in judged}


def verdict(j: dict | None) -> str:
    if not j:
        return "not judged"
    if j["type"] in ANSWERED:
        facts = j["facts"] or []
        cov = sum(f == "correct" for f in facts)
        return f"facts {cov}/{len(facts)}; wrong fact {'yes' if 'wrong' in facts else 'no'}; wrong group {'yes' if j['wrong_group'] else 'no'}"
    if j["type"] == "clarify":
        return "question about a branch detail" if j["asks_branch_attribute"] else "question about another detail"
    return "right referral" if j["right_referral"] else "referral without the right office/step"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {c["case_id"]: c for c in hyu_suite.load_cases("test")}
    v2 = {(r["preset"].split("_")[0], r["qid"]): r for r in csv.DictReader(open(RESULTS_DIR / "test-final" / "hyu_test_v2_per_case.csv"))}
    v3 = load_v3()
    branch = sorted(q for q, c in cases.items() if c["expected_behavior"] in ("conditional_answer", "clarify"))
    rows = []
    for q in branch:
        c, j = cases[q], v3.get(("A0", q), {})
        content_ok = (j.get("type") == "conditional_answer" and j.get("conditions_match") is True) or (j.get("type") == "clarify" and j.get("asks_branch_attribute") is True)
        row = {"case": q, "question": c["question"], "earlier_turns": " / ".join(t["text"] for t in c.get("session_history") or []),
               "missing_detail": ", ".join(c.get("branch_attributes") or []), "label": c["expected_behavior"], "label_accepts": ", ".join(c["acceptable_behaviors"]),
               "aaes_right_reply_type_v2": v2[("A0", q)]["acceptable"] == "True", "aaes_right_content_v3": content_ok,
               "aaes_reply": (j.get("reply") or "")[:400]}  # fmt: skip
        for m in ALL:
            row[f"{m}_type_v2"] = v2[(m, q)]["predicted"]
        for m in JUDGED:
            row[f"{m}_v3"] = verdict(v3.get((m, q)))
        rows.append(row)
    with (OUT / "part1a_branching_cases.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("1a: AAES right on reply type", sum(r["aaes_right_reply_type_v2"] for r in rows), "| on content", sum(r["aaes_right_content_v3"] for r in rows))

    wg = lambda m, q: bool((j := v3.get((m, q))) and j["type"] in ANSWERED and j["wrong_group"])  # noqa: E731
    out = {"source": "evaluator v3 judgments of saved test-1 replies (post-hoc); wrong group is judged only for answered replies",
           "wrong_group_count": {m: sum(wg(m, q) for q in cases) for m in JUDGED},
           "answered_count": {m: sum(1 for q in cases if (j := v3.get((m, q))) and j["type"] in ANSWERED) for m in JUDGED}, "per_baseline": {}}  # fmt: skip
    for b in ("B0", "R15", "R16"):
        base_wrong_aaes_not = sorted(q for q in cases if wg(b, q) and not wg("A0", q))
        aaes_wrong_base_not = sorted(q for q in cases if wg("A0", q) and not wg(b, q))
        out["per_baseline"][b] = {"baseline_wrong_group_aaes_not": base_wrong_aaes_not, "aaes_wrong_group_baseline_not": aaes_wrong_base_not,
                                  "aaes_reply_type_where_baseline_wrong": dict(Counter(v2[("A0", q)]["predicted"] for q in base_wrong_aaes_not))}  # fmt: skip
    stated = [q for q in cases if any(wg(b, q) for b in ("B0", "R15", "R16")) and (cases[q].get("stated_profile") or cases[q].get("session_history"))]
    out["stated_group_and_baseline_wrong_group"] = [{"case": q, "question": cases[q]["question"], "earlier_turns": [t["text"] for t in cases[q].get("session_history") or []],
                                                     "stated_profile": cases[q].get("stated_profile"), "wrong_group_baselines": [b for b in ("B0", "R15", "R16") if wg(b, q)],
                                                     "aaes_type_v2": v2[("A0", q)]["predicted"], "aaes_wrong_group": wg("A0", q)} for q in sorted(stated)]  # fmt: skip
    (OUT / "part1b_wrong_group.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "stated_group_and_baseline_wrong_group"}, indent=1))
    for s in out["stated_group_and_baseline_wrong_group"]:
        print(s["case"], s["stated_profile"], s["earlier_turns"], "|", s["question"], "| wrong:", s["wrong_group_baselines"], "| A0", s["aaes_type_v2"], s["aaes_wrong_group"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
