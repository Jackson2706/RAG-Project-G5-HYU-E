"""Deck v2 Section 6: run each demo candidate 3 times in compare mode (B0, R16, A0) through the API the UI uses.

Run from Sources/ with the backend at http://127.0.0.1:8000:  python scripts/demo_trials.py
-> Report/slides/deck_v2/demo_trials.csv (scenario, run, method, reply type, reply text, seconds, A0 trace facts).

Questions are dev questions or new wording for the demo, never test-1 questions. Reply types use evaluator v2 unchanged
(evaluation/reply_action.py: rules, then qwen3.5:4b). No code, preset or prompt is changed to make a scenario work.
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation import reply_action  # noqa: E402

API, INDEX = "http://127.0.0.1:8000/api", "hyu_20261110_97dc1269_r5"
OUT = Path(__file__).resolve().parents[2] / "Report" / "slides" / "deck_v2" / "demo_trials.csv"
METHODS = {"B0": "B0_BASIC_DENSE_RAG", "R16": "R16_PROMPTED_CONDITIONAL", "A0": "A0_AAES"}
SCENARIOS = [  # (id, what it should show, history, question, source)
    ("S1", "conditional answer", [], "Which insurance rules apply to me?", "dev T14-132"),
    ("S2", "useful question (campus)", [], "How do I book the international student counseling program?", "dev T14-017"),
    ("S3", "useful question (degree, year, TOPIK)", [], "Can I work part time here?", "dev T14-130"),
    ("S4", "useful question (degree level)", [], "Does my insurance change after my visa switches from D-4 to D-2?", "dev T14-120"),
    ("S5", "two-turn: profile first, then a direct answer", ["I'm a second-year undergraduate at the ERICA campus and I have TOPIK level 3."],
     "Can I work part time here?", "new turn 1 + dev T14-130"),
    ("S6", "two-turn: campus stated, then a direct answer", ["I'm a Seoul campus student."],
     "How do I book the international student counseling program?", "new turn 1 + dev T14-017"),
    ("S7", "old notice vs current notice", [], "How much is health insurance this year?", "dev T14-147"),
    ("S8", "honest limitation (unneeded campus question)", [], "Is there a winter school for international students?", "dev T14-042"),
]  # fmt: skip


def main() -> int:
    presets = {p["id"]: p for p in json.load(urllib.request.urlopen(f"{API}/pipeline/presets"))["presets"]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ["scenario", "shows", "source", "history", "question", "run", "method", "reply_type", "aaes_action", "aaes_reason",
              "branch_attributes", "clarify_attribute", "seconds", "reply"]  # fmt: skip
    with OUT.open("w", newline="", encoding="utf-8") as handle, httpx.Client(base_url="http://localhost:11434", timeout=180) as ollama:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for sid, shows, history, question, source in SCENARIOS:
            for run in (1, 2, 3):
                for name, pid in METHODS.items():  # compare mode: sequential, one column after another
                    body = {"question": question, "stages": presets[pid]["stages"], "index_id": INDEX, "history": history}
                    request = urllib.request.Request(f"{API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
                    start = time.time()
                    trace = json.load(urllib.request.urlopen(request, timeout=600))
                    seconds = round(time.time() - start, 1)
                    reply = trace.get("answer") or trace.get("error") or ""
                    kind = reply_action.rule_label(reply) or reply_action.llm_label(reply, ollama)[0]
                    sufficiency = next((s for s in trace.get("stages", []) if s["stage_id"] == "evidence_sufficiency"), {})
                    signals = ((sufficiency.get("output") or {}).get("signals") or {}) if sufficiency.get("status") == "completed" else {}
                    writer.writerow({"scenario": sid, "shows": shows, "source": source, "history": " / ".join(history), "question": question,
                                     "run": run, "method": name, "reply_type": kind, "aaes_action": trace.get("action") or "",
                                     "aaes_reason": signals.get("reason", ""), "branch_attributes": ",".join(signals.get("branch_attributes") or []),
                                     "clarify_attribute": signals.get("clarify_attribute") or "", "seconds": seconds, "reply": reply})  # fmt: skip
                    handle.flush()
                    print(sid, run, name, kind, trace.get("action"), seconds, reply[:80].replace("\n", " "), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
