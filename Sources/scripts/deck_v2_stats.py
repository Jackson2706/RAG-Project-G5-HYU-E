"""Post-hoc numbers for the deck v2 brief (Section 5a), from saved test-1 replies and existing judgments. No system run.

Run from Sources/:  python scripts/deck_v2_stats.py   # -> Report/slides/deck_v2/section5_posthoc.json

1. Branching cases (15 labelled conditional answer or clarify), evaluator v2 acceptability: AAES vs each retrieval
   baseline, paired counts (AAES right & baseline wrong, the reverse) and a two-sided exact McNemar p.
2. Right conditions on the same 15 cases, evaluator v3 (a conditional answer whose conditions match, or a question about
   a branch attribute): same paired counts. Only B0, R15, R16 (and G0, G1) were judged by v3; R5 and R9S were not.
3. Among answered replies (v3): share with at least one wrong fact, share with wrong-group information; paired bootstrap
   95% CI and permutation p for AAES minus each judged baseline (cases where both answered are not required: each rate
   is over that method's own answered replies, so the comparison is not like-for-like).
4. Replies stating at least one wrong fact over all 121 cases, per judged method.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation.metrics.stats import paired_compare  # noqa: E402

from app.config import REPORT_DIR, RESULTS_DIR  # noqa: E402

BRANCHING, ANSWERED = ("conditional_answer", "clarify"), ("answer", "conditional_answer")
BASELINES = ("B0", "R5", "R9S", "R15", "R16")
JUDGED = ("B0", "R15", "R16", "G0", "G1")


def mcnemar(b: int, c: int) -> float:
    """Two-sided exact McNemar p. b = 9, c = 1 -> 0.0215."""
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n) if n else 1.0


def wrong_fact_answered(rows):
    pool = [r for r in rows if r and r["type"] in ANSWERED and r["facts"]]
    return sum("wrong" in r["facts"] for r in pool) / len(pool) if pool else 0.0


def wrong_group_answered(rows):
    pool = [r for r in rows if r and r["type"] in ANSWERED and r["wrong_group"] is not None]
    return sum(bool(r["wrong_group"]) for r in pool) / len(pool) if pool else 0.0


def main() -> int:
    v2 = {(r["preset"].split("_")[0], r["qid"]): r for r in csv.DictReader(open(RESULTS_DIR / "test-final" / "hyu_test_v2_per_case.csv"))}
    raw = RESULTS_DIR / "quality_v3" / "raw"
    key = {k["id"]: k for k in map(json.loads, open(raw / "key.jsonl"))}
    items = {i["id"]: i for i in map(json.loads, open(raw / "items_test.jsonl"))}
    judged = {j["id"]: j for f in sorted((raw / "judgments").glob("test_*.jsonl")) for j in map(json.loads, open(f))}
    v3 = {(key[i]["preset"].split("_")[0], key[i]["case_id"]): {**judged[i], "type": items[i]["reply_type"]} for i in judged}
    qids = sorted(q for p, q in v2 if p == "A0")
    branch = [q for q in qids if v2[("A0", q)]["expected"] in BRANCHING]
    out: dict = {"source": "test-1 saved replies; evaluator v2 per-case table and evaluator v3 judgments (post-hoc)", "branching_cases": len(branch)}

    ok = lambda p, q: v2[(p, q)]["acceptable"] == "True"  # noqa: E731
    out["1_branching_acceptable_v2"] = []
    for b in BASELINES:
        x, y = sum(ok("A0", q) and not ok(b, q) for q in branch), sum(ok(b, q) and not ok("A0", q) for q in branch)
        out["1_branching_acceptable_v2"].append({"baseline": b, "aaes_right_baseline_wrong": x, "baseline_right_aaes_wrong": y, "mcnemar_p": mcnemar(x, y),
                                                 "aaes_right": sum(ok("A0", q) for q in branch), "baseline_right": sum(ok(b, q) for q in branch)})  # fmt: skip

    def right_conditions(p, q):
        j = v3.get((p, q))
        return bool(j) and ((j["type"] == "conditional_answer" and j["conditions_match"] is True) or (j["type"] == "clarify" and j["asks_branch_attribute"] is True))

    out["2_branching_right_conditions_v3"] = []
    for b in ("B0", "R15", "R16"):
        x, y = sum(right_conditions("A0", q) and not right_conditions(b, q) for q in branch), sum(right_conditions(b, q) and not right_conditions("A0", q) for q in branch)
        out["2_branching_right_conditions_v3"].append({"baseline": b, "aaes_right_baseline_wrong": x, "baseline_right_aaes_wrong": y, "mcnemar_p": mcnemar(x, y),
                                                       "aaes_right": sum(right_conditions("A0", q) for q in branch), "baseline_right": sum(right_conditions(b, q) for q in branch)})  # fmt: skip

    out["3_among_answered_v3"] = []
    for b in ("B0", "R15", "R16"):
        a, c = [v3.get(("A0", q)) for q in qids], [v3.get((b, q)) for q in qids]
        for name, stat in (("wrong fact", wrong_fact_answered), ("wrong group", wrong_group_answered)):
            res = paired_compare(a, c, stat)
            out["3_among_answered_v3"].append({"metric": name, "baseline": b, "aaes": stat(a), "baseline_value": stat(c), **res})
    out["3_answered_counts"] = {p: sum(1 for q in qids if (j := v3.get((p, q))) and j["type"] in ANSWERED) for p in ("A0", *JUDGED)}

    out["4_wrong_fact_all_121_v3"] = {p: sum(1 for q in qids if (j := v3.get((p, q))) and j["type"] in ANSWERED and "wrong" in (j["facts"] or [])) / len(qids)
                                      for p in ("A0", *JUDGED)}  # fmt: skip
    path = REPORT_DIR / "slides" / "deck_v2" / "section5_posthoc.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    assert abs(mcnemar(9, 1) - 0.0215) < 1e-3
    raise SystemExit(main())
