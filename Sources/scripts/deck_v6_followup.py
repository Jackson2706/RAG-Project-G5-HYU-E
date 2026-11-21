"""Deck v6 Task 1 dev check (post-hoc, dev only): Task 2 "reply only" again, with follow-up resolution on.

Run from Sources/ (MongoDB, Qdrant, Ollama), after the v6 fix:
  python scripts/deck_v6_followup.py run          # -> Report/slides/deck_v4/followup_v6/runs.jsonl (resumable)
  python scripts/deck_v6_followup.py items        # -> followup_v6/judge/items.jsonl + key.jsonl (blind, shuffled)
  python scripts/deck_v6_followup.py merge        # judgments_part{1,2,3}.jsonl (GPT-6 Sol, v3 prompt) -> judgments.jsonl
  python scripts/deck_v6_followup.py compare      # -> followup_v6/summary.json, scores.csv, content.json, transcripts.md

Same 39 personas Phase 4 judged in "reply only", same reply templates (deck_v4_followup.reply_for), same model and
index; A0_AAES and AP_RRRL. Each reply is sent with the previous reply's clarify marker and followup_resolution=True,
so a detail-only reply answers the earlier question. Stops after 3 questions, as in Task 2. Reply types: evaluator v2.
"""

from __future__ import annotations

import asyncio
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deck_v4_followup as f  # noqa: E402

from app.rag.pipeline import run_rag  # noqa: E402
from app.rag.presets import preset_config  # noqa: E402
from evaluation import reply_action  # noqa: E402
from evaluation.reports import load_jsonl  # noqa: E402

OUT = f.OUT.parent / "followup_v6"
PRESETS = ["A0_AAES", "AP_RRRL"]
ASKS = ("CLARIFY", "CONFIRM")


def judged_personas() -> list[dict]:
    """The 39 personas Phase 4 judged in the reply-only condition, in the same order."""
    pids = {k["pid"] for k in load_jsonl(f.OUT / "judge" / "key.jsonl") if k["system"] == "A0 reply_only"}
    return [p for p in f.personas() if p["pid"] in pids]


class Runner(f.Runner):
    def __init__(self) -> None:
        super().__init__()
        self.path = OUT / "runs.jsonl"
        self.done = {r["key"]: r for r in load_jsonl(self.path)} if self.path.exists() else {}

    async def chat(self, preset: str, question: str, history: list[str], followup: dict | None = None) -> dict:  # type: ignore[override]
        key = json.dumps([preset, question, history, followup])
        if key in self.done:
            return self.done[key]
        config = preset_config(preset, {"generation": {"params": f.GEN}})
        start = time.time()
        trace = await run_rag(question, config, self.services, save_trace=False, history=history, followup=followup, followup_resolution=True)
        reply = trace.get("answer") or trace.get("error") or ""
        signals = (trace.get("decision") or {}).get("signals") or {}
        cited = []
        for s in trace.get("sources") or []:
            if s.get("cited"):
                doc = self.db.chunks.find_one({"chunk_id": s["chunk_id"]}, {"text": 1, "_id": 0}) or {}
                cited.append({"label": s["label"], "text": (doc.get("text") or s.get("excerpt") or "")[:1500]})
        rec = {"key": key, "preset": preset, "question": question, "history": history, "followup_sent": followup, "action": trace.get("action"),
               "ask": signals.get("clarify_attribute") or signals.get("confirm_attribute"), "clarify": trace.get("clarify"),
               "resolved": trace.get("followup"), "reply_type": reply_action.rule_label(reply) or reply_action.llm_label(reply, self.ollama)[0],
               "seconds": round(time.time() - start, 1), "reply": reply, "cited": cited, "error": trace.get("error")}  # fmt: skip
        OUT.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.done[key] = rec
        print(preset[:7], rec["action"], rec["reply_type"], rec["seconds"], question[:50], "| answering:", (rec["resolved"] or {}).get("answering", "")[:40], flush=True)
        return rec


async def conversation(r: Runner, preset: str, p: dict) -> dict:
    """Reply only: after each question the student sends only the templated detail (with the clarify marker)."""
    turns, answers, asked = [], [], []
    rec = await r.chat(preset, p["question"], [])
    while True:
        turns.append(rec)
        if rec["action"] not in ASKS or len(asked) == f.MAX_ASKS or not rec["ask"]:
            break
        asked.append(rec["ask"])
        answers.append(f.reply_for(rec["ask"], p["profile"]))
        rec = await r.chat(preset, answers[-1], [p["question"], *answers[:-1]], rec.get("clarify"))
    return {**p, "system": f"{preset.split('_')[0]} reply_only (v6 fix)", "final": turns[-1], "user_turns": 1 + len(answers), "asked": asked,
            "asked_first": turns[0]["action"] in ASKS, "transcript": turns}  # fmt: skip


async def conversations() -> list[dict]:
    r = Runner()
    return [await conversation(r, preset, p) for p in judged_personas() for preset in PRESETS]


def items() -> int:
    convs = asyncio.run(conversations())  # every turn is in runs.jsonl after `run`: no system call
    random.Random(6).shuffle(convs)
    (OUT / "judge").mkdir(parents=True, exist_ok=True)
    keys = []
    with (OUT / "judge" / "items.jsonl").open("w", encoding="utf-8") as handle:
        for n, c in enumerate(convs, 1):
            fin = c["final"]
            item = {"id": f"V{n:03d}", "question": fin["question"], "session_history": fin["history"], "gold_profile": c["profile"],
                    "branch_attributes": [a for a in c["branch_attributes"] if a not in set(c["asked"])], "required_facts": c["required_facts"],
                    "gold_evidence": c["gold_evidence"][:4000], "inapplicable_evidence": c["inapplicable_evidence"][:2000],
                    "reply_type": fin["reply_type"], "reply": fin["reply"][:3000], "cited_sources": fin["cited"]}  # fmt: skip
            if fin.get("resolved"):  # the reply answered the earlier question: show the judge which question it answers
                item["question"] = fin["resolved"]["answering"]
                item["session_history"] = [*fin["history"], fin["question"]]
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            keys.append({"id": item["id"], "pid": c["pid"], "system": c["system"], "user_turns": c["user_turns"], "expect_refer": c["expect_refer"],
                         "asked_first": c["asked_first"]})  # fmt: skip
    (OUT / "judge" / "key.jsonl").write_text("".join(json.dumps(k) + "\n" for k in keys))
    print("items", len(keys))
    return 0


def compare() -> int:
    f.OUT = OUT
    f.compare()
    key = load_jsonl(OUT / "judge" / "key.jsonl")
    item = {i["id"]: i for i in load_jsonl(OUT / "judge" / "items.jsonl")}
    judged = {j["id"]: j for j in load_jsonl(OUT / "judge" / "judgments.jsonl")}
    rows = []
    for system in sorted({k["system"] for k in key}):
        recs = [k for k in key if k["system"] == system]
        answered = [k for k in recs if item[k["id"]]["reply_type"] in ("answer", "conditional_answer")]
        facts = [x for k in answered for x in judged[k["id"]]["facts"] or []]
        asked = [k for k in recs if k["asked_first"]]
        rows.append({"system": system, "personas": len(recs), "asked_first": len(asked), "answered": len(answered),
                     "answered_after_one_reply": sum(k["user_turns"] == 2 and item[k["id"]]["reply_type"] in ("answer", "conditional_answer") for k in asked),
                     "facts_covered": round(sum(x == "correct" for x in facts) / len(facts), 3) if facts else None,
                     "wrong_fact": round(sum(x == "wrong" for x in facts) / len(facts), 3) if facts else None,
                     "wrong_group": round(statistics.fmean(bool(judged[k["id"]]["wrong_group"]) for k in answered), 3) if answered else None,
                     "turns_mean": round(statistics.fmean(k["user_turns"] for k in recs), 2)})  # fmt: skip
    before = [r for r in json.loads((f.OUT.parent / "followup" / "content_v5.json").read_text())["systems"] if r["system"] == "A0 reply_only"]
    meta = json.loads((OUT / "judge" / "judgments.meta.json").read_text())
    (OUT / "content.json").write_text(json.dumps({"label": "post-hoc, dev only; judged by GPT-6 Sol (v3 prompt)", "judge": meta,
                                                  "phase4_A0_reply_only": before, "v6": rows}, indent=1) + "\n")  # fmt: skip
    print(json.dumps(rows, indent=1))
    return 0


def transcripts() -> int:
    convs = {(c["pid"], c["system"]): c for c in asyncio.run(conversations())}
    lines = ["# Follow-up transcripts with the v6 fix (post-hoc, dev only)", ""]
    for (pid, system), c in sorted(convs.items()):
        if "counsel" not in c["question"].lower() and pid != "T14-033":
            continue
        lines += [f"## {pid} · {system} · persona {json.dumps(c['profile'])}", ""]
        for t in c["transcript"]:
            note = f"  _(answering your earlier question: {t['resolved']['answering']})_" if t.get("resolved") else ""
            lines += [f"**Student**: {t['question']}{note}", "", f"**HYU Compass** ({t['action']}, {t['seconds']} s): " + t["reply"].replace("\n", " "), ""]
    (OUT / "transcripts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


async def run() -> int:
    await conversations()
    return 0


def merge() -> int:
    f.OUT = OUT
    return f.merge_judgments()


if __name__ == "__main__":
    cmd = sys.argv[1]
    raise SystemExit(asyncio.run(run()) if cmd == "run" else {"items": items, "merge": merge, "compare": compare, "transcripts": transcripts}[cmd]())
