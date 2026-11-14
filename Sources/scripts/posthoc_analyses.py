"""Post-hoc analyses of a finished HYU run, under evaluator v1 and v2 (amendment A34). EXPLORATORY, not pre-registered.

Run from Sources/:
  python scripts/posthoc_analyses.py test-final     # -> Report/results/test-final/posthoc_{by_expected,branch_detection,a0}.csv + posthoc.md

Reads only the run's per-case tables (hyu_<split>_per_case.csv, hyu_<split>_v2_per_case.csv) and A0's saved replies
in raw/ (for the clarify attribute named in the CLARIFY template). Never reads labels directly.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import RESULTS_DIR  # noqa: E402

BRANCHING = ("conditional_answer", "clarify")
EXPECTED = ("answer", "abstain", "conditional_answer", "clarify")
CLARIFY_TEMPLATE = re.compile(r"^The answer depends on your ([^.]+)\. Which applies to you")


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def ratio(a: int, b: int) -> str:
    return f"{a / b:.3f}" if b else "N/A"


def branch_detection(rows: list[dict]) -> dict:
    """Positive = needs branching. [(cond, clarify), (answer, cond), (cond, answer)] -> precision 1/2, recall 1/2."""
    tp = sum(r["expected"] in BRANCHING and r["predicted"] in BRANCHING for r in rows)
    pred = sum(r["predicted"] in BRANCHING for r in rows)
    pos = sum(r["expected"] in BRANCHING for r in rows)
    return {"tp": tp, "predicted_branching": pred, "expected_branching": pos, "precision": ratio(tp, pred), "recall": ratio(tp, pos)}


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p from the discordant counts. b = 9, c = 1 -> 22/1024 = 0.0215."""
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n) if n else 1.0


def main(run_id: str) -> int:
    run = RESULTS_DIR / run_id
    split = next(run.glob("hyu_*_slices.csv")).name.split("_")[1]
    by_expected, detection = [], []
    for version, name in (("v1", f"hyu_{split}_per_case.csv"), ("v2", f"hyu_{split}_v2_per_case.csv")):
        per_preset = defaultdict(list)
        for r in read(run / name):
            per_preset[r["preset"]].append(r)
        for preset, rows in per_preset.items():
            for expected in EXPECTED:
                group = [r for r in rows if r["expected"] == expected]
                by_expected.append({"evaluator": version, "preset": preset, "expected": expected, "cases": len(group),
                                    "acceptable_rate": ratio(sum(r["acceptable"] == "True" for r in group), len(group))})  # fmt: skip
            detection.append({"evaluator": version, "preset": preset, **branch_detection(rows)})
    write(run / "posthoc_by_expected.csv", by_expected)
    write(run / "posthoc_branch_detection.csv", detection)

    # A0 under v1 (its own actions): which attribute CLARIFY asks for, and CLARIFY on cases labelled abstain.
    a0 = {r["qid"]: r for r in read(run / f"hyu_{split}_per_case.csv") if r["preset"] == "A0_AAES"}
    replies = {}
    for line in (run / "raw" / "hyu" / split / "A0_AAES__-.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if rec["status"] == "completed":
            replies[rec["qid"]] = rec
    attributes = Counter(m.group(1) for q, rec in replies.items() if rec["action"] == "CLARIFY" and (m := CLARIFY_TEMPLATE.match(rec["answer"])))
    clarify = [q for q, rec in replies.items() if rec["action"] == "CLARIFY"]
    a0_rows = [{"count": "A0 CLARIFY", "value": len(clarify)},
               *({"count": f"A0 CLARIFY asks for {a}", "value": n} for a, n in attributes.most_common()),
               {"count": "A0 CLARIFY on cases labelled abstain", "value": sum(a0[q]["expected"] == "abstain" for q in clarify)},
               {"count": "cases labelled abstain", "value": sum(r["expected"] == "abstain" for r in a0.values())},
               {"count": "cases that need branching (labelled conditional_answer or clarify)",
                "value": sum(r["expected"] in BRANCHING for r in a0.values())},
               {"count": "cases", "value": len(a0)}]  # fmt: skip
    write(run / "posthoc_a0.csv", a0_rows)

    lines = [f"# {run_id}: post-hoc analyses (EXPLORATORY, amendment A34)", "",
             "Not pre-registered. From the per-case tables of evaluator v1 and v2 and A0's saved replies. "
             "Source: `scripts/posthoc_analyses.py`.", "", "## Acceptable-action rate per expected behaviour", "",
             "| evaluator | preset | " + " | ".join(f"{e} (n)" for e in EXPECTED) + " |", "|---|---|" + "---|" * len(EXPECTED)]  # fmt: skip
    table = defaultdict(dict)
    for r in by_expected:
        table[(r["evaluator"], r["preset"])][r["expected"]] = f"{r['acceptable_rate']} ({r['cases']})"
    lines += [f"| {v} | {p} | " + " | ".join(cells.get(e, "") for e in EXPECTED) + " |" for (v, p), cells in sorted(table.items())]
    lines += ["", "## Branch detection (positive = conditional_answer or clarify)", "",
              "| evaluator | preset | TP | predicted | expected | precision | recall |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['evaluator']} | {r['preset']} | {r['tp']} | {r['predicted_branching']} | {r['expected_branching']} | {r['precision']} | {r['recall']} |"
              for r in sorted(detection, key=lambda r: (r["evaluator"], r["preset"]))]  # fmt: skip
    lines += ["", "## A0 counts", "", "| count | value |", "|---|---|"] + [f"| {r['count']} | {r['value']} |" for r in a0_rows]
    # Branch hits on the cases that need branching (v2): A0 vs A3 overlap, A0 vs R16 exact McNemar (post hoc, not Holm-corrected).
    v2 = {(r["preset"], r["qid"]): r for r in read(run / f"hyu_{split}_v2_per_case.csv")}
    need = sorted(q for (p, q), r in v2.items() if p == "A0_AAES" and r["expected"] in BRANCHING)
    hits = {p: {q for q in need if (p, q) in v2 and v2[(p, q)]["predicted"] in BRANCHING} for p in {p for p, _ in v2}}
    if "A3_AAES_ALWAYS_CLARIFY" in hits:
        a0, a3 = hits["A0_AAES"], hits["A3_AAES_ALWAYS_CLARIFY"]
        lines += ["", "## A0 vs A3 branch hits (v2, cases that need branching)", "",
                  f"A0 {len(a0)}, A3 {len(a3)}, both {len(a0 & a3)}, A0 only {len(a0 - a3)}, A3 only {len(a3 - a0)} "
                  f"(A3 only: {', '.join(sorted(a3 - a0)) or 'none'}), of {len(need)} cases."]  # fmt: skip
    if "R16_PROMPTED_CONDITIONAL" in hits:
        b, c = len(hits["A0_AAES"] - hits["R16_PROMPTED_CONDITIONAL"]), len(hits["R16_PROMPTED_CONDITIONAL"] - hits["A0_AAES"])
        lines += ["", "## A0 vs R16 branch hits, exact McNemar (post hoc, exploratory, not Holm-corrected)", "",
                  f"{len(need)} cases; discordant: A0 only {b}, R16 only {c}; two-sided exact p = {mcnemar_exact(b, c):.4f}."]
    if "A0b_AAES_SPEC_FIXED" in hits:  # dev-03: A0b's actions on the branching cases (raw records keep no stage details)
        lines += ["", "## A0b on the cases that need branching", "", "| case | expected | A0b action | A0b reply starts |", "|---|---|---|---|"]
        for line in (run / "raw" / "hyu" / split / "A0b_AAES_SPEC_FIXED__-.jsonl").read_text().splitlines():
            rec = json.loads(line)
            if rec["status"] == "completed" and rec["qid"] in need:
                lines.append(f"| {rec['qid']} | {v2[('A0b_AAES_SPEC_FIXED', rec['qid'])]['expected']} | {rec['action']} | {rec['answer'][:60].replace('|', '/')} |")
    (run / "posthoc.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {run}/posthoc.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "test-final"))
