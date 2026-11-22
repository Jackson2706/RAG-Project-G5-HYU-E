"""Deck v4 Task 1: rehearse the demo in compare mode (B0, R16, A0), index r5, 3 runs per scenario.

Run from Sources/ with the backend at http://127.0.0.1:8000:  python scripts/deck_v4_demo.py
-> Report/slides/deck_v4/demo_trials_v4.csv (one row per turn; appends, so a stopped run resumes where it ended).

Cold = run 1 of each scenario, after the Ollama models were unloaded (keep_alive 0), so the model loads again.
Warm = runs 2 and 3. Questions are dev questions or new demo wording, never test-1. Reply types use evaluator v2
unchanged. No code, preset or prompt is changed to make a scenario work; every run is logged.
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
OUT = Path(__file__).resolve().parents[2] / "Report" / "slides" / "deck_v4" / "demo_trials_v4.csv"
METHODS = {"B0": "B0_BASIC_DENSE_RAG", "R16": "R16_PROMPTED_CONDITIONAL", "A0": "A0_AAES"}
COUNSEL = "How do I book the international student counseling program?"
SCENARIOS = [  # (id, what it should show, source, turns sent one after another in one conversation)
    ("S1", "answer per case, then the Execution tab", "dev T14-132", ["Which insurance rules apply to me?"]),
    ("S2", "asks the campus; after 'Seoul' answers by degree level, campus remembered", "dev T14-017 + new turn",
     [COUNSEL, "I'm a Seoul campus student.", COUNSEL]),
    ("S3", "visa change D-4 to D-2", "dev T14-120", ["Does my insurance change after my visa switches from D-4 to D-2?"]),
    ("S4", "referral to the right campus office", "dev T14-184", ["Which partner schools offer a one-semester visit taught fully in English?"]),
    ("S4b", "referral naming the campus office (campus stated)", "dev T14-184, new wording",
     ["I'm a Seoul campus student. Which partner schools offer a one-semester visit taught fully in English?"]),
    ("S4c", "referral naming the campus office (new question; picked from s4_candidates.csv)", "new",
     ["I'm a Seoul campus student. Can I bring my pet dog into the dormitory?"]),
    ("S5", "backup failure: unneeded campus question", "dev T14-042", ["Is there a winter school for international students?"]),
]  # fmt: skip
FIELDS = ["scenario", "shows", "source", "run", "timing", "method", "turn", "history", "question", "reply_type", "aaes_action",
          "aaes_reason", "clarify_attribute", "profile_campus", "seconds", "reply"]  # fmt: skip


def unload_models(ollama: httpx.Client) -> None:
    for m in ollama.get("/api/ps").json().get("models", []):
        ollama.post("/api/generate", json={"model": m["name"], "keep_alive": 0})


def main() -> int:
    presets = {p["id"]: p for p in json.load(urllib.request.urlopen(f"{API}/pipeline/presets"))["presets"]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
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
                for name, pid in METHODS.items():  # compare mode: one column after another
                    history: list[str] = []
                    for turn, question in enumerate(turns, 1):
                        body = {"question": question, "stages": presets[pid]["stages"], "index_id": INDEX, "history": history}
                        req = urllib.request.Request(f"{API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
                        start = time.time()
                        trace = json.load(urllib.request.urlopen(req, timeout=900))
                        seconds = round(time.time() - start, 1)
                        reply = trace.get("answer") or trace.get("error") or ""
                        kind = reply_action.rule_label(reply) or reply_action.llm_label(reply, ollama)[0]
                        stages = {s["stage_id"]: s for s in trace.get("stages", [])}
                        suff = stages.get("evidence_sufficiency", {})
                        signals = ((suff.get("output") or {}).get("signals") or {}) if suff.get("status") == "completed" else {}
                        prof = ((stages.get("query_understanding", {}).get("output") or {}).get("profile") or {}).get("campus") or {}
                        writer.writerow({"scenario": sid, "shows": shows, "source": source, "run": run, "timing": "cold" if run == 1 else "warm",
                                         "method": name, "turn": turn, "history": " / ".join(history), "question": question, "reply_type": kind,
                                         "aaes_action": trace.get("action") or "", "aaes_reason": signals.get("reason", ""),
                                         "clarify_attribute": signals.get("clarify_attribute") or "",
                                         "profile_campus": f"{prof.get('status', '')} {','.join(prof.get('values') or [])}".strip(),
                                         "seconds": seconds, "reply": reply})  # fmt: skip
                        handle.flush()
                        print(sid, run, name, turn, kind, trace.get("action"), seconds, reply[:70].replace("\n", " "), flush=True)
                        history.append(question)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
