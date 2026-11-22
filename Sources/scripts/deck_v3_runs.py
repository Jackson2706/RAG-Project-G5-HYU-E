"""Deck v3 live runs (new questions and demo traces only; never test-1). Backend at http://127.0.0.1:8000, index r5.

Run from Sources/:
  python scripts/deck_v3_runs.py illustrative   # 10 new questions x (B0, R15, R16, A0) x 3 runs -> deck_v3/illustrative_runs.csv
  python scripts/deck_v3_runs.py traces         # full A0 traces: S1, and the two-turn S2 -> S6 -> deck_v3/trace_S1.json, trace_S2_S6.json

Every run is logged, including the ones AAES loses. Reply types use evaluator v2 unchanged. No code, preset or prompt
is changed. Cited chunk texts are read from MongoDB (read-only) for the evaluator v3 judge.
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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import reply_action  # noqa: E402

API, INDEX = "http://127.0.0.1:8000/api", "hyu_20261110_97dc1269_r5"
OUT = Path(__file__).resolve().parents[2] / "Report" / "slides" / "deck_v3"
METHODS = {"B0": "B0_BASIC_DENSE_RAG", "R15": "R15_SELF_QUERY", "R16": "R16_PROMPTED_CONDITIONAL", "A0": "A0_AAES"}


def chat(presets, pid, question, history=()):
    body = {"question": question, "stages": presets[pid]["stages"], "index_id": INDEX, "history": list(history)}
    request = urllib.request.Request(f"{API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    start = time.time()
    trace = json.load(urllib.request.urlopen(request, timeout=900))
    return trace, round(time.time() - start, 1)


def illustrative(presets):
    from app.config import get_settings
    from app.database import Database

    settings = get_settings()
    chunks = Database.connect(settings).for_index(INDEX).chunks
    questions = json.load(open(OUT / "illustrative_questions.json"))
    fields = ["id", "question", "run", "method", "reply_type", "aaes_action", "aaes_reason", "branch_attributes", "clarify_attribute",
              "seconds", "reply", "cited"]  # fmt: skip
    with (OUT / "illustrative_runs.csv").open("w", newline="", encoding="utf-8") as handle, httpx.Client(base_url="http://localhost:11434", timeout=180) as ollama:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for q in questions:
            for run in (1, 2, 3):
                for name, pid in METHODS.items():
                    trace, seconds = chat(presets, pid, q["question"])
                    reply = trace.get("answer") or trace.get("error") or ""
                    kind = reply_action.rule_label(reply) or reply_action.llm_label(reply, ollama)[0]
                    signals = next(((s.get("output") or {}).get("signals") or {} for s in trace["stages"] if s["stage_id"] == "evidence_sufficiency"
                                    and s["status"] == "completed"), {})  # fmt: skip
                    cited = []
                    for s in trace.get("sources") or []:
                        if s.get("cited"):
                            doc = chunks.find_one({"chunk_id": s["chunk_id"]}, {"text": 1, "_id": 0}) or {}
                            cited.append({"label": s["label"], "title": s["title"], "url": s["source_uri"], "text": (doc.get("text") or s.get("excerpt") or "")[:1500]})
                    writer.writerow({"id": q["id"], "question": q["question"], "run": run, "method": name, "reply_type": kind,
                                     "aaes_action": trace.get("action") or "", "aaes_reason": signals.get("reason", ""),
                                     "branch_attributes": ",".join(signals.get("branch_attributes") or []), "clarify_attribute": signals.get("clarify_attribute") or "",
                                     "seconds": seconds, "reply": reply, "cited": json.dumps(cited, ensure_ascii=False)})  # fmt: skip
                    handle.flush()
                    print(q["id"], run, name, kind, trace.get("action"), seconds, flush=True)


def traces(presets):
    s1, _ = chat(presets, "A0_AAES", "Which insurance rules apply to me?")
    (OUT / "trace_S1.json").write_text(json.dumps(s1, indent=1, ensure_ascii=False))
    question = "How do I book the international student counseling program?"
    s2, _ = chat(presets, "A0_AAES", question)
    s6, _ = chat(presets, "A0_AAES", question, ["I'm a Seoul campus student."])
    (OUT / "trace_S2_S6.json").write_text(json.dumps({"S2_no_history": s2, "S6_with_history": s6}, indent=1, ensure_ascii=False))
    print("S1", s1.get("action"), "| S2", s2.get("action"), "| S6", s6.get("action"))


def main() -> int:
    presets = {p["id"]: p for p in json.load(urllib.request.urlopen(f"{API}/pipeline/presets"))["presets"]}
    {"illustrative": illustrative, "traces": traces}[sys.argv[1]](presets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
