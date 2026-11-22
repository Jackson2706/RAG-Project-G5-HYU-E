"""A35 Step 4: AG vs its base on a dev run, scored with evaluator v2 (unchanged). GO / NO-GO.

Run from Sources/ after `python -m evaluation.rescore --run-id dev-04`:
  python scripts/ag_gate.py dev-04          # -> Report/results/dev-04/ag_gate.json

Definitions, fixed before the results were seen (STATUS 2026-11-14, A35 Step 4):
  fired             AG's record has an action (the guard replaced the base reply)
  fix / break       base reply not acceptable and AG's acceptable / the reverse (v2 labels, per case)
  override precision  fired cases where AG is acceptable / fired cases
  GO                AG acceptable rate >= base acceptable rate AND override precision >= 0.4
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import RESULTS_DIR  # noqa: E402

BASE, AG, A0 = "R16_PROMPTED_CONDITIONAL", "AG_AAES_GUARD", "A0_AAES"


def main(run_id: str) -> int:
    run = RESULTS_DIR / run_id
    rows = {(r["preset"], r["qid"]): r for r in csv.DictReader(open(run / "hyu_dev_v2_per_case.csv"))}
    raw = {json.loads(line)["qid"]: json.loads(line) for line in open(run / "raw" / "hyu" / "dev" / f"{AG}__-.jsonl")}
    qids = sorted(q for p, q in rows if p == AG)
    ok = lambda p, q: rows[(p, q)]["acceptable"] == "True"  # noqa: E731
    fired = [q for q in qids if raw[q].get("action")]
    summary = {p: next(r for r in csv.DictReader(open(run / "hyu_dev_v2_slices.csv")) if r["preset"] == p and r["slice"] == "all")
               for p in (BASE, A0, AG)}  # fmt: skip
    out = {"run": run_id, "cases": len(qids), "fired": len(fired), "fired_cases": fired,
           "fixes": [q for q in qids if ok(AG, q) and not ok(BASE, q)], "breaks": [q for q in qids if ok(BASE, q) and not ok(AG, q)],
           "override_precision": sum(ok(AG, q) for q in fired) / len(fired) if fired else None,
           **{f"acceptable_{p}": float(summary[p]["acceptable_rate"]) for p in summary},
           **{f"unnecessary_question_{p}": summary[p]["unnecessary_clarification_rate"] for p in summary}}  # fmt: skip
    out["go"] = bool(out["acceptable_" + AG] >= out["acceptable_" + BASE] and (out["override_precision"] or 0) >= 0.4)
    (run / "ag_gate.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "dev-04"))
