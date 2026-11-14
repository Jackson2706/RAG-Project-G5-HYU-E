"""The pre-registered test-2 analysis (Report/results/PREREG_test2.md), fixed before the run. Evaluator v2.

Run from Sources/ after the single test-2 run and `python -m evaluation.rescore --run-id test2-final`:
  python scripts/test2_analysis.py test2-final      # -> Report/results/test2-final/prereg_test2.{json,md}

Primary: AG vs base (R16), acceptable-action rate, paired bootstrap 95% CI and permutation p.
Secondary (Holm across the five): branching precision, branching recall, wrong-branch answers (AER), unnecessary-
question rate, acceptable rate on refusal cases (labelled abstain). Labels are read with the runner's reader.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402
from evaluation.metrics.stats import holm, paired_compare  # noqa: E402

from app.config import RESULTS_DIR  # noqa: E402

AG, BASE = "AG_AAES_GUARD", "R16_PROMPTED_CONDITIONAL"
BRANCHING = ("conditional_answer", "clarify")


def ratio(num: int, den: int) -> float:
    return num / den if den else 0.0


# Each statistic takes a list of per-case tuples (expected, acceptable list, predicted, aer or None) and returns a rate.
def acceptable(rows):
    return ratio(sum(p in acc for _, acc, p, _ in rows), len(rows))


def branch_precision(rows):
    return ratio(sum(p in BRANCHING and e in BRANCHING for e, _, p, _ in rows), sum(p in BRANCHING for _, _, p, _ in rows))


def branch_recall(rows):
    return ratio(sum(p in BRANCHING and e in BRANCHING for e, _, p, _ in rows), sum(e in BRANCHING for e, _, _, _ in rows))


def aer(rows):
    defined = [a for _, _, _, a in rows if a is not None]
    return ratio(sum(defined), len(defined))


def unnecessary_question(rows):
    pool = [p for _, acc, p, _ in rows if "clarify" not in acc]
    return ratio(sum(p == "clarify" for p in pool), len(pool))


def refusal_acceptable(rows):
    return acceptable([r for r in rows if r[0] == "abstain"])


SECONDARY = {"branching precision": branch_precision, "branching recall": branch_recall, "wrong-branch answers (AER)": aer,
             "unnecessary-question rate": unnecessary_question, "acceptable rate on refusal cases": refusal_acceptable}  # fmt: skip


def main(run_id: str) -> int:
    run = RESULTS_DIR / run_id
    cases = {c["case_id"]: c for c in hyu_suite.load_cases("test2")}
    per = {(r["preset"], r["qid"]): r for r in csv.DictReader(open(run / "hyu_test2_v2_per_case.csv"))}
    qids = sorted(q for p, q in per if p == AG and (BASE, q) in per)

    def rows(preset):
        out = []
        for q in qids:
            r = per[(preset, q)]
            value = r["aer"] if r["aer"] not in ("", "None", "N/A") else None
            out.append((cases[q]["expected_behavior"], cases[q]["acceptable_behaviors"], r["predicted"], None if value is None else int(float(value))))
        return out

    ag, base = rows(AG), rows(BASE)
    result = {"run": run_id, "cases": len(qids), "evaluator": "v2", "primary": {"metric": "acceptable-action rate", "AG": acceptable(ag),
              "base": acceptable(base), **paired_compare(ag, base, acceptable)}, "secondary": []}  # fmt: skip
    for name, stat in SECONDARY.items():
        result["secondary"].append({"metric": name, "AG": stat(ag), "base": stat(base), **paired_compare(ag, base, stat)})
    for row, p in zip(result["secondary"], holm([r["p"] for r in result["secondary"]]), strict=True):
        row["p_holm"] = p
    (run / "prereg_test2.json").write_text(json.dumps(result, indent=1) + "\n")
    lines = [f"# {run_id}: pre-registered analysis (PREREG_test2.md), evaluator v2", "", f"{len(qids)} cases, AG vs base R16.", "",
             "| Metric | AG | R16 | diff | 95% CI | p | Holm p |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in [result["primary"], *result["secondary"]]:
        lines.append(f"| {r['metric']} | {r['AG']:.3f} | {r['base']:.3f} | {r['diff']:+.3f} | [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] | "
                     f"{r['p']:.4f} | {('%.4f' % r['p_holm']) if 'p_holm' in r else 'n/a'} |")  # fmt: skip
    (run / "prereg_test2.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "test2-final"))
