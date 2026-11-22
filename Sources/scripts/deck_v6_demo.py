"""Deck v6 Task 2: rehearse the live demo in compare mode (B0, R16, AAES+ = AP_RRRL), index r5, 3 runs per scenario.

Run from Sources/ with the backend at http://127.0.0.1:8000 (follow-up resolution on, the app default):
  python scripts/deck_v6_demo.py   -> Report/slides/deck_v4/demo_trials_v6.csv (one row per turn; appends, resumable)

Same procedure as deck_v4_demo.py: run 1 cold (Ollama models unloaded first), runs 2-3 warm; reply types by
evaluator v2. As in the UI's compare mode, every turn goes to every column, and each column sends back its own
previous reply's clarify marker. Questions are dev questions or new demo wording; D4 uses the dev wording, never the
held-out T2-011 wording.
"""

from __future__ import annotations

import csv
import json
import time
import urllib.request

import httpx

import deck_v4_demo as v4
from deck_v4_demo import API, INDEX, reply_action, unload_models

OUT = v4.OUT.with_name("demo_trials_v6.csv")
METHODS = {"B0": "B0_BASIC_DENSE_RAG", "R16": "R16_PROMPTED_CONDITIONAL", "AAES+": "AP_RRRL"}
SCENARIOS = [  # (id, what it should show, source, turns)
    ("D1", "answer per case; then the Execution tab", "dev T14-132", ["Which insurance rules apply to me?"]),
    ("D2", "AAES+ asks the campus; the reply answers the original question", "dev T14-017 + reply",
     [v4.COUNSEL, "I'm a Seoul campus student."]),
    ("D3", "referral naming the Seoul OIA office", "new (s4_candidates.csv)", ["I'm a Seoul campus student. Can I bring my pet dog into the dormitory?"]),
    ("D4", "known failure: unneeded campus question (dev wording; T2-011 is held out)", "dev T14-042",
     ["Is there a winter school for international students?"]),
]  # fmt: skip
FIELDS = ["scenario", "shows", "source", "run", "timing", "method", "turn", "question", "answering", "reply_type", "aaes_action",
          "clarify_attribute", "seconds", "reply"]  # fmt: skip


def main() -> int:
    presets = {p["id"]: p for p in json.load(urllib.request.urlopen(f"{API}/pipeline/presets"))["presets"]}
    done = {(r["scenario"], r["run"]) for r in csv.DictReader(OUT.open())} if OUT.exists() else set()
    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as handle, httpx.Client(base_url="http://localhost:11434", timeout=180) as ollama:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        for sid, shows, source, turns in SCENARIOS:
            for run in (1, 2, 3):
                if (sid, str(run)) in done:
                    continue
                if run == 1:
                    unload_models(ollama)
                history: list[str] = []
                marker: dict[str, dict | None] = dict.fromkeys(METHODS)
                for turn, question in enumerate(turns, 1):
                    for name, pid in METHODS.items():  # compare mode: one column after another
                        body = {"question": question, "stages": presets[pid]["stages"], "index_id": INDEX, "history": history, "followup": marker[name]}
                        req = urllib.request.Request(f"{API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
                        start = time.time()
                        trace = json.load(urllib.request.urlopen(req, timeout=900))
                        seconds = round(time.time() - start, 1)
                        reply = trace.get("answer") or trace.get("error") or ""
                        kind = reply_action.rule_label(reply) or reply_action.llm_label(reply, ollama)[0]
                        signals = (trace.get("decision") or {}).get("signals") or {}
                        marker[name] = trace.get("clarify")
                        writer.writerow({"scenario": sid, "shows": shows, "source": source, "run": run, "timing": "cold" if run == 1 else "warm",
                                         "method": name, "turn": turn, "question": question, "answering": (trace.get("followup") or {}).get("answering", ""),
                                         "reply_type": kind, "aaes_action": trace.get("action") or "", "clarify_attribute": signals.get("clarify_attribute") or "",
                                         "seconds": seconds, "reply": reply})  # fmt: skip
                        handle.flush()
                        print(sid, run, name, turn, kind, trace.get("action"), seconds, reply[:70].replace("\n", " "), flush=True)
                    history.append(question)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
