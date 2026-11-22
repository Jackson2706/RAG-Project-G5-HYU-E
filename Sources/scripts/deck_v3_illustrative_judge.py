"""Deck v3 Part 1c: judge items for the illustrative runs, and the comparison once judged.

Run from Sources/:
  python scripts/deck_v3_illustrative_judge.py items     # -> deck_v3/judge/items.jsonl + key.jsonl (blind, shuffled)
  python scripts/deck_v3_illustrative_judge.py compare   # after the judge wrote deck_v3/judge/judgments.jsonl -> deck_v3/illustrative_comparison.json

The judge uses the evaluator v3 prompt unchanged (Sources/evaluation/judge_v3_prompt.md). Reference facts are the
per-group answers in illustrative_questions.json ("For <group>: <answer>"), gold evidence is the verified quotes, the
branch attributes are the missing details. Score per reply (fixed before judging):
  2 = conditional answer whose conditions match, or a question about a missing detail
  1 = an answer with at least one correct fact and no wrong fact and no wrong-group information
  0 = anything else (wrong fact, wrong group, an unrelated question, a referral although every group has an answer)
A referral scores 1 only for I10 (the Seoul side is not on the pages). AAES vs a baseline per question: compare the mean
score over the 3 runs (higher = better, equal = same, lower = worse).
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "Report" / "slides" / "deck_v3"
J = OUT / "judge"


def items() -> int:
    questions = {q["id"]: q for q in json.load(open(OUT / "illustrative_questions.json"))}
    quotes = {r["id"]: r for r in csv.DictReader(open(OUT / "quotes.csv"))}
    rows = list(csv.DictReader(open(OUT / "illustrative_runs.csv")))
    random.Random(36).shuffle(rows)
    J.mkdir(exist_ok=True)
    keys = []
    with (J / "items.jsonl").open("w", encoding="utf-8") as handle:
        for n, r in enumerate(rows, 1):
            q = questions[r["id"]]
            ids = [i for g in q["groups"] for i in g["quote_ids"]]
            item = {"id": f"X{n:03d}", "question": q["question"], "session_history": [], "gold_profile": None, "branch_attributes": q["missing"],
                    "required_facts": [f"For {g['group']}: {g['answer']}" for g in q["groups"]],
                    "gold_evidence": " | ".join(f"{quotes[i]['quote']} ({quotes[i]['url']})" for i in dict.fromkeys(ids)), "inapplicable_evidence": "",
                    "reply_type": r["reply_type"], "reply": r["reply"][:3000],
                    "cited_sources": [{"label": c["label"], "text": c["text"]} for c in json.loads(r["cited"] or "[]")]}  # fmt: skip
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            keys.append({"id": item["id"], "qid": r["id"], "method": r["method"], "run": r["run"]})
    (J / "key.jsonl").write_text("".join(json.dumps(k) + "\n" for k in keys))
    print("items", len(keys))
    return 0


def score(qid: str, kind: str, j: dict) -> int:
    if kind == "conditional_answer" and j.get("conditions_match") is True or kind == "clarify" and j.get("asks_branch_attribute") is True:
        return 2
    if kind in ("answer", "conditional_answer") and "correct" in (j.get("facts") or []) and "wrong" not in (j.get("facts") or []) and not j.get("wrong_group"):
        return 1
    if kind == "abstain" and qid == "I10":
        return 1
    return 0


def compare() -> int:
    key = {k["id"]: k for k in map(json.loads, open(J / "key.jsonl"))}
    item = {i["id"]: i for i in map(json.loads, open(J / "items.jsonl"))}
    judged = {j["id"]: j for j in map(json.loads, open(J / "judgments.jsonl"))}
    s = defaultdict(list)
    per = []
    for i, j in judged.items():
        k = key[i]
        sc = score(k["qid"], item[i]["reply_type"], j)
        s[(k["qid"], k["method"])].append(sc)
        per.append({**k, "reply_type": item[i]["reply_type"], "score": sc, "facts": j.get("facts"), "wrong_group": j.get("wrong_group"),
                    "conditions_match": j.get("conditions_match"), "asks_branch_attribute": j.get("asks_branch_attribute"), "right_referral": j.get("right_referral")})  # fmt: skip
    qids = sorted({k[0] for k in s})
    mean = {k: sum(v) / len(v) for k, v in s.items()}
    out = {"scoring": "2 right conditions or a question on a missing detail; 1 correct partial answer, no wrong fact or group; 0 otherwise (mean of 3 runs)",
           "mean_score": {q: {m: round(mean[(q, m)], 2) for m in ("B0", "R15", "R16", "A0")} for q in qids}, "aaes_vs": {}}  # fmt: skip
    for b in ("B0", "R15", "R16"):
        res = {"better": [q for q in qids if mean[(q, "A0")] > mean[(q, b)]], "same": [q for q in qids if mean[(q, "A0")] == mean[(q, b)]],
               "worse": [q for q in qids if mean[(q, "A0")] < mean[(q, b)]]}  # fmt: skip
        out["aaes_vs"][b] = {k: {"count": len(v), "questions": v} for k, v in res.items()}
    (OUT / "illustrative_comparison.json").write_text(json.dumps(out, indent=1) + "\n")
    with (OUT / "illustrative_scores.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per[0]))
        writer.writeheader()
        writer.writerows(sorted(per, key=lambda r: (r["qid"], r["method"], r["run"])))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    assert score("I01", "clarify", {"asks_branch_attribute": True}) == 2 and score("I01", "answer", {"facts": ["correct", "missing"], "wrong_group": False}) == 1
    raise SystemExit({"items": items, "compare": compare}[sys.argv[1]]())
