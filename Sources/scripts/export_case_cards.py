"""Material for presentation case cards (A35 Step 2): label fields, evidence text and saved replies of named cases.

Run from Sources/:
  python scripts/export_case_cards.py test-final test T14-088 T14-121 > /tmp/cards.json
  python scripts/export_case_cards.py dev-03 dev T14-132 T14-120

Labels are read through evaluation.hyu_suite.load_cases (the runner's reader); replies come from the run's raw/
(the latest completed record per preset). Nothing is re-run. Evidence text is cut from the frozen snapshot by span.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite  # noqa: E402
from evaluation.reports import load_jsonl  # noqa: E402

from app.config import RESULTS_DIR  # noqa: E402

PRESETS = ("B0_BASIC_DENSE_RAG", "R16_PROMPTED_CONDITIONAL", "A0_AAES", "A0b_AAES_SPEC_FIXED", "AG_AAES_GUARD")


def main(run_id: str, split: str, case_ids: list[str]) -> int:
    cases = {c["case_id"]: c for c in hyu_suite.load_cases(split) if c["case_id"] in case_ids}
    docs = {r["doc_id"]: r for r in load_jsonl(hyu_suite.snapshot_dir(next(iter(cases.values()))["snapshot_id"]) / "documents.jsonl")}
    folder = RESULTS_DIR / run_id / "raw" / "hyu" / split
    replies = {}
    for preset in PRESETS:
        path = folder / f"{preset}__-.jsonl"
        if path.exists():
            replies[preset] = {r["qid"]: r for r in load_jsonl(path) if r.get("status") == "completed"}

    def spans(field, case):
        return [{**{k: s.get(k) for k in ("doc_id", "branch", "note") if s.get(k)}, "campus": docs[s["doc_id"]].get("campus"),
                 "title": docs[s["doc_id"]].get("title"), "text": docs[s["doc_id"]]["text"][s["char_start"]:s["char_end"]]}
                for s in case.get(field) or []]  # fmt: skip

    out = []
    for cid in case_ids:
        case = cases[cid]
        out.append({"case_id": cid, "slice": case.get("slice"), "question": case["question"], "session_history": case.get("session_history"),
                    "stated_profile": case.get("stated_profile"), "expected": case["expected_behavior"],
                    "acceptable": case["acceptable_behaviors"], "branch_attributes": case.get("branch_attributes"),
                    "required_facts": case.get("required_facts"), "gold": spans("gold_evidence", case),
                    "inapplicable": spans("inapplicable_evidence", case),
                    "replies": {p: {"action": r[cid].get("action"), "answer": r[cid]["answer"]} for p, r in replies.items() if cid in r}})  # fmt: skip
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
