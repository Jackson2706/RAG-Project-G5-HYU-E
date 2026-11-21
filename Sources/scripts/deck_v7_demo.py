"""Deck v7 Task 1: rehearse the per-case candidate T14-130 (3 runs) and D1-D3 (1 run each), cleanup and follow-up on.

Run from Sources/ with the backend at http://127.0.0.1:8000 (clean_reply and followup_resolution on, the app defaults):
  python scripts/deck_v7_demo.py   -> Report/slides/deck_v4/demo_trials_v7.csv (one row per turn and column; resumable)

Same procedure as deck_v6_demo.py (compare mode B0, R16, AAES+ = AP_RRRL; run 1 cold; reply types by evaluator v2),
plus the cited sources of each reply (label, title, URL, excerpt) so the stated facts can be checked against the page.
Never runs test-1 T14-088 ("How many hours can an international student work part time?").
"""

from __future__ import annotations

import csv
import json
import time
import urllib.request

import httpx

import deck_v6_demo as v6
from deck_v4_demo import API, INDEX, reply_action, unload_models

OUT = v6.OUT.with_name("demo_trials_v7.csv")
SCENARIOS = [("T14-130", "per-case candidate: part-time work", "dev T14-130", ["Can I work part time here?"], 3)] + [
    (sid, shows, source, turns, 1) for sid, shows, source, turns in v6.SCENARIOS if sid in ("D1", "D2", "D3")]
FIELDS = [*v6.FIELDS, "raw_reply", "cited"]


def main() -> int:
    presets = {p["id"]: p for p in json.load(urllib.request.urlopen(f"{API}/pipeline/presets"))["presets"]}
    done = {(r["scenario"], r["run"]) for r in csv.DictReader(OUT.open())} if OUT.exists() else set()
    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as handle, httpx.Client(base_url="http://localhost:11434", timeout=180) as ollama:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        for sid, shows, source, turns, runs in SCENARIOS:
            for run in range(1, runs + 1):
                if (sid, str(run)) in done:
                    continue
                if run == 1:
                    unload_models(ollama)
                history: list[str] = []
                marker: dict[str, dict | None] = dict.fromkeys(v6.METHODS)
                for turn, question in enumerate(turns, 1):
                    for name, pid in v6.METHODS.items():
                        body = {"question": question, "stages": presets[pid]["stages"], "index_id": INDEX, "history": history, "followup": marker[name]}
                        req = urllib.request.Request(f"{API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
                        start = time.time()
                        trace = json.load(urllib.request.urlopen(req, timeout=900))
                        seconds = round(time.time() - start, 1)
                        reply = trace.get("answer") or trace.get("error") or ""
                        kind = reply_action.rule_label(reply) or reply_action.llm_label(reply, ollama)[0]
                        signals = (trace.get("decision") or {}).get("signals") or {}
                        marker[name] = trace.get("clarify")
                        cited = [{"label": s["label"], "title": s.get("title"), "url": s.get("source_uri"), "excerpt": s.get("excerpt")}
                                 for s in trace.get("sources") or [] if s.get("cited")]  # fmt: skip
                        writer.writerow({"scenario": sid, "shows": shows, "source": source, "run": run, "timing": "cold" if run == 1 else "warm",
                                         "method": name, "turn": turn, "question": question, "answering": (trace.get("followup") or {}).get("answering", ""),
                                         "reply_type": kind, "aaes_action": trace.get("action") or "", "clarify_attribute": signals.get("clarify_attribute") or "",
                                         "seconds": seconds, "reply": reply, "raw_reply": trace.get("raw_answer") or "", "cited": json.dumps(cited, ensure_ascii=False)})  # fmt: skip
                        handle.flush()
                        print(sid, run, name, turn, kind, trace.get("action"), seconds, reply[:70].replace("\n", " "), flush=True)
                    history.append(question)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
