"""Deck v4 Task 2: what happens after AAES asks. Dev cases and the deck-v3 illustrative personas only (never test-1).

Run from Sources/ (MongoDB, Qdrant, Ollama; headless, the same run_rag the app and the runner use):
  python scripts/deck_v4_followup.py run       # -> Report/slides/deck_v4/followup/runs.jsonl (resumable)
  python scripts/deck_v4_followup.py items     # -> followup/judge/items.jsonl + key.jsonl (blind, shuffled) for the v3 judge
  python scripts/deck_v4_followup.py compare   # after followup/judge/judgments.jsonl exists -> followup/summary.json, scores.csv

Personas: a dev case's gold_profile; an illustrative group's profile (followup/personas_illustrative.json).
Whenever A0 asks (CLARIFY or CONFIRM), the student replies with a fixed template for the asked attribute (REPLY).
  reply-only  : turn 2 = the reply alone, history [question] (what a student types in the UI); repeat while A0 asks.
  reply+re-ask: the student replies and asks the question again, history [question, reply] (the demo S2 path).
Both stop after 3 questions from A0. Baselines B0, R5, R9S, R15, R16 answer in one turn, without the detail and with
the persona's details up front ("I'm a Seoul campus student. <question>"), details = labelled branch attributes plus
the attributes A0 asked. A0 with the details up front is run too. Config: hyu.yaml generation (qwen3.5:4b,
temperature 0, seed 42, thinking off), index r5. Reply types: evaluator v2 unchanged.

Score of a final reply (fixed before judging), from the frozen v3 judge's fields:
  expected answer : 2 = every required fact correct, none wrong, no wrong group, conditions match if per case;
                    1 = at least one fact correct, none wrong, no wrong group; 0 otherwise (a question or referral too).
  expected referral (dev abstain cases, I10 Seoul): 2 = referral naming the right office; 1 = referral without it;
                    answers 1 if at least one fact correct and none wrong, else 0; a question 0.
"""

from __future__ import annotations

import asyncio
import csv
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from evaluation import hyu_suite, reply_action  # noqa: E402
from evaluation.reports import load_jsonl  # noqa: E402

from app.config import REPORT_DIR, get_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.ollama import OllamaClient  # noqa: E402
from app.rag.pipeline import run_rag  # noqa: E402
from app.rag.presets import preset_config  # noqa: E402
from app.rag.schemas import Services  # noqa: E402

OUT = REPORT_DIR / "slides" / "deck_v4" / "followup"
V3 = REPORT_DIR / "slides" / "deck_v3"
INDEX = "hyu_20261110_97dc1269_r5"
GEN = {"model": "qwen3.5:4b", "temperature": 0.0, "seed": 42, "thinking": "off"}
BASELINES = ["B0_BASIC_DENSE_RAG", "R5_HYBRID_CROSS_ENCODER", "R9S_SCOPE_PREFILTER", "R15_SELF_QUERY", "R16_PROMPTED_CONDITIONAL"]
MAX_ASKS = 3
SAY = {"undergraduate": "an undergraduate", "master": "a master's", "doctoral": "a doctoral", "language_program": "a language program",
       "non_degree": "a non-degree", "degree_seeking": "a degree-seeking", "exchange": "an exchange", "visiting": "a visiting"}
STATUS = {"applicant": "I'm applying for admission.", "admitted_not_enrolled": "I was admitted but have not enrolled yet.",
          "enrolled": "I'm currently enrolled.", "leave_of_absence": "I'm on leave of absence.",
          "completed_coursework": "I finished my coursework.", "graduating": "I'm graduating this semester."}
ORD = {"1": "first", "2": "second", "3": "third", "4": "fourth"}
KOREAN = {"pass": "I passed the Korean language standard.", "fail": "I did not meet the Korean language standard.",
          "exempt": "I'm exempt from the Korean language standard."}  # fmt: skip


def reply_for(attribute: str, profile: dict) -> str:
    """The student's answer to "which applies to you: ...", one fixed template per attribute."""
    v = profile.get(attribute)
    if v is None:
        return "I'm not sure."
    return {"campus": lambda: f"I'm a {'Seoul' if v == 'seoul' else 'ERICA'} campus student.",
            "degree_level": lambda: f"I'm {SAY[v]} student.", "student_type": lambda: f"I'm {SAY[v]} student.",
            "year": lambda: f"I'm in my {ORD[v]} year.", "visa": lambda: f"My visa is {v}.",
            "topik_level": lambda: "I don't have TOPIK." if v == "none" else f"I have TOPIK level {v}.",
            "english_track": lambda: "I'm in an English-track program." if v == "yes" else "I'm in a Korean-track program.",
            "academic_status": lambda: STATUS[v], "korean_standard": lambda: KOREAN[v]}[attribute]()  # fmt: skip


def personas() -> list[dict]:
    """One row per (question, persona) with the persona's required facts, evidence and expected kind."""
    docs = {d["doc_id"]: d["text"] for d in load_jsonl(hyu_suite.snapshot_dir("hyu-20261110-97dc1269") / "documents.jsonl")}
    rows = []
    for c in hyu_suite.load_cases("dev"):
        if c.get("session_history"):
            continue  # multi-session cases already carry earlier turns; the follow-up starts from a fresh chat
        gold = " | ".join(docs.get(g["doc_id"], "")[g["char_start"]:g["char_end"]] for g in c["gold_evidence"])
        bad = " | ".join(docs.get(g["doc_id"], "")[g["char_start"]:g["char_end"]] for g in c.get("inapplicable_evidence") or [])
        rows.append({"pid": c["case_id"], "qid": c["case_id"], "source": "dev", "question": c["question"],
                     "profile": {k: v for k, v in (c.get("gold_profile") or {}).items() if v}, "branch_attributes": c.get("branch_attributes") or [],
                     "required_facts": c["required_facts"], "gold_evidence": gold, "inapplicable_evidence": bad,
                     "expect_refer": c["expected_behavior"] == "abstain"})  # fmt: skip
    questions = {q["id"]: q for q in json.load(open(V3 / "illustrative_questions.json"))}
    quotes = {r["id"]: r for r in csv.DictReader(open(V3 / "quotes.csv"))}
    for p in json.load(open(OUT / "personas_illustrative.json"))["personas"]:
        q = questions[p["qid"]]
        g = q["groups"][p["group"]]
        rows.append({"pid": f"{p['qid']}-g{p['group']}", "qid": p["qid"], "source": "illustrative", "question": q["question"], "profile": p["profile"],
                     "branch_attributes": [a for a in q["missing"] if a in reply_action_vocab()], "required_facts": [g["answer"]],
                     "gold_evidence": " | ".join(f"{quotes[i]['quote']} ({quotes[i]['url']})" for i in g["quote_ids"]),
                     "inapplicable_evidence": " | ".join(f"{quotes[i]['quote']}" for o in q["groups"] if o is not g for i in o["quote_ids"] if i not in g["quote_ids"]),
                     "expect_refer": "Not stated" in g["answer"]})  # fmt: skip
    return rows


def reply_action_vocab() -> set[str]:
    from app.rag.applicability import VOCABULARY

    return set(VOCABULARY)


class Runner:
    def __init__(self) -> None:
        settings = get_settings().model_copy(update={"embedding_device": "auto"})
        self.db = Database.connect(settings).for_index(INDEX)
        self.services = Services(db=self.db, ollama=OllamaClient(settings.ollama_base_url, timeout=settings.ollama_timeout), settings=settings)
        self.ollama = httpx.Client(base_url=settings.ollama_base_url, timeout=180)
        self.path = OUT / "runs.jsonl"
        self.done = {r["key"]: r for r in load_jsonl(self.path)} if self.path.exists() else {}

    async def chat(self, preset: str, question: str, history: list[str]) -> dict:
        key = json.dumps([preset, question, history])
        if key in self.done:
            return self.done[key]
        config = preset_config(preset, {"generation": {"params": GEN}} if "generation" in preset_config(preset) else {})
        start = time.time()
        trace = await run_rag(question, config, self.services, save_trace=False, history=history)
        reply = trace.get("answer") or trace.get("error") or ""
        signals = next(((s.get("output") or {}).get("signals") or {} for s in trace["stages"] if s["stage_id"] == "evidence_sufficiency"
                        and s["status"] == "completed"), {})  # fmt: skip
        cited = []
        for s in trace.get("sources") or []:
            if s.get("cited"):
                doc = self.db.chunks.find_one({"chunk_id": s["chunk_id"]}, {"text": 1, "_id": 0}) or {}
                cited.append({"label": s["label"], "text": (doc.get("text") or s.get("excerpt") or "")[:1500]})
        rec = {"key": key, "preset": preset, "question": question, "history": history, "action": trace.get("action"),
               "ask": signals.get("clarify_attribute") or signals.get("confirm_attribute"), "reason": signals.get("reason"),
               "reply_type": reply_action.rule_label(reply) or reply_action.llm_label(reply, self.ollama)[0],
               "seconds": round(time.time() - start, 1), "reply": reply, "cited": cited, "error": trace.get("error")}  # fmt: skip
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.done[key] = rec
        print(preset[:4], rec["action"], rec["reply_type"], rec["seconds"], question[:60], "|", history[-1:] if history else "", flush=True)
        return rec


def turn(mode: str, question: str, answers: list[str]) -> tuple[str, list[str]]:
    """(message, history) of the next user turn after the student gave `answers` to A0's questions."""
    if not answers:
        return question, []
    if mode == "reply_only":  # the student only replies
        return answers[-1], [question, *answers[:-1]]
    return question, [question, *answers]  # reply_reask: the student replies, then asks the question again


async def follow(r: Runner, p: dict, mode: str) -> list[str]:
    """Run A0's conversation for one persona; return the attributes A0 asked."""
    answers, asked = [], []
    while True:
        rec = await r.chat("A0_AAES", *turn(mode, p["question"], answers))
        if rec["action"] not in ("CLARIFY", "CONFIRM") or len(asked) == MAX_ASKS or not rec["ask"]:
            return asked
        asked.append(rec["ask"])
        answers.append(reply_for(rec["ask"], p["profile"]))


async def run() -> int:
    r = Runner()
    for p in personas():
        first = await r.chat("A0_AAES", p["question"], [])
        if first["action"] not in ("CLARIFY", "CONFIRM"):
            continue  # Task 2 covers the questions where AAES asks
        asked_a = await follow(r, p, "reply_only")
        asked_b = await follow(r, p, "reply_reask")
        details = list(dict.fromkeys([*p["branch_attributes"], *asked_a, *asked_b]))
        upfront = " ".join(reply_for(a, p["profile"]) for a in details if a in p["profile"]) + " " + p["question"]
        await r.chat("A0_AAES", upfront, [])
        for b in BASELINES:
            await r.chat(b, p["question"], [])
            await r.chat(b, upfront, [])
    return 0


def conversations() -> list[dict]:
    """Every judged final reply, rebuilt from runs.jsonl (no system call)."""
    runs = {r["key"]: r for r in load_jsonl(OUT / "runs.jsonl")}

    def get(preset, question, history):
        return runs.get(json.dumps([preset, question, history]))

    out = []
    for p in personas():
        first = get("A0_AAES", p["question"], [])
        if not first or first["action"] not in ("CLARIFY", "CONFIRM"):
            continue
        for mode in ("reply_only", "reply_reask"):
            answers, asked, turns = [], [], []
            while (rec := get("A0_AAES", *turn(mode, p["question"], answers))) is not None:
                turns.append(rec)
                if rec["action"] not in ("CLARIFY", "CONFIRM") or len(asked) == MAX_ASKS or not rec["ask"]:
                    break
                asked.append(rec["ask"])
                answers.append(reply_for(rec["ask"], p["profile"]))
            user_turns = 1 + len(answers) + (len(answers) > 0 and mode == "reply_reask")  # reply+re-ask: the re-asked question is one more turn
            out.append({**p, "system": f"A0 {mode}", "final": turns[-1], "user_turns": user_turns, "asked": asked,
                        "transcript": [{"student": t["question"], "history": t["history"], "assistant": t["reply"], "action": t["action"]} for t in turns]})  # fmt: skip
        details = list(dict.fromkeys([*p["branch_attributes"], *out[-1]["asked"], *out[-2]["asked"]]))
        upfront = " ".join(reply_for(a, p["profile"]) for a in details if a in p["profile"]) + " " + p["question"]
        for preset in ["A0_AAES", *BASELINES]:
            for label, question in (("one turn", p["question"]), ("details up front", upfront)):
                if preset == "A0_AAES" and label == "one turn":
                    out.append({**p, "system": "A0 one turn (asks)", "final": first, "user_turns": 1, "asked": [], "transcript": []})
                    continue
                rec = get(preset, question, [])
                if rec:
                    out.append({**p, "system": f"{preset.split('_')[0]} {label}", "final": rec, "user_turns": 1, "asked": [], "transcript": []})
    return out


def items() -> int:
    convs = conversations()
    random.Random(4).shuffle(convs)
    (OUT / "judge").mkdir(exist_ok=True)
    keys = []
    with (OUT / "judge" / "items.jsonl").open("w", encoding="utf-8") as handle:
        for n, c in enumerate(convs, 1):
            f = c["final"]
            stated = set(c["asked"]) | ({a for a in c["profile"] if c["system"].endswith("up front")} & set(c["branch_attributes"]))
            item = {"id": f"F{n:03d}", "question": f["question"], "session_history": f["history"], "gold_profile": c["profile"],
                    "branch_attributes": [a for a in c["branch_attributes"] if a not in stated], "required_facts": c["required_facts"],
                    "gold_evidence": c["gold_evidence"][:4000], "inapplicable_evidence": c["inapplicable_evidence"][:2000],
                    "reply_type": f["reply_type"], "reply": f["reply"][:3000], "cited_sources": f["cited"]}  # fmt: skip
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            keys.append({"id": item["id"], "pid": c["pid"], "system": c["system"], "user_turns": c["user_turns"], "expect_refer": c["expect_refer"]})
    (OUT / "judge" / "key.jsonl").write_text("".join(json.dumps(k) + "\n" for k in keys))
    print("items", len(keys))
    return 0


def score(kind: str, j: dict, expect_refer: bool) -> int:
    facts = j.get("facts") or []
    clean = "wrong" not in facts and not j.get("wrong_group")
    if kind == "abstain":
        return (2 if j.get("right_referral") else 1) if expect_refer else 0
    if kind not in ("answer", "conditional_answer"):
        return 0
    if expect_refer:
        return 1 if "correct" in facts and clean else 0
    if facts and all(x == "correct" for x in facts) and clean and j.get("conditions_match") is not False:
        return 2
    return 1 if "correct" in facts and clean else 0


def compare() -> int:
    key = {k["id"]: k for k in load_jsonl(OUT / "judge" / "key.jsonl")}
    item = {i["id"]: i for i in load_jsonl(OUT / "judge" / "items.jsonl")}
    judged = {j["id"]: j for j in load_jsonl(OUT / "judge" / "judgments.jsonl")}
    rows = []
    for i, j in judged.items():
        k = key[i]
        rows.append({**k, "reply_type": item[i]["reply_type"], "score": score(item[i]["reply_type"], j, k["expect_refer"]), "facts": j.get("facts"),
                     "wrong_group": j.get("wrong_group"), "conditions_match": j.get("conditions_match"), "right_referral": j.get("right_referral")})  # fmt: skip
    by = defaultdict(list)
    for r in rows:
        by[r["system"]].append(r)
    summary = {"scoring": __doc__.split("Score of a final reply")[1].strip(), "personas": len({r["pid"] for r in rows}), "systems": {}}
    for system, rs in sorted(by.items()):
        summary["systems"][system] = {"n": len(rs), "mean_score": round(sum(r["score"] for r in rs) / len(rs), 3),
                                      "score_2": sum(r["score"] == 2 for r in rs), "score_0": sum(r["score"] == 0 for r in rs),
                                      "mean_user_turns": round(sum(r["user_turns"] for r in rs) / len(rs), 2),
                                      "final_reply_types": dict(sorted(_count(r["reply_type"] for r in rs).items()))}  # fmt: skip
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    with (OUT / "scores.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["pid"], r["system"])))
    print(json.dumps(summary["systems"], indent=1))
    return 0


def _count(values) -> dict:
    out: dict = defaultdict(int)
    for v in values:
        out[v] += 1
    return dict(out)


def transcripts() -> int:
    """Readable two-turn transcripts of every A0 follow-up -> followup/transcripts.md."""
    lines = ["# AAES follow-up transcripts (reply-only and reply+re-ask)", ""]
    for c in conversations():
        if not c["system"].startswith("A0 reply"):
            continue
        lines += [f"## {c['pid']} · {c['system']} · persona {json.dumps(c['profile'])}", ""]
        for t in c["transcript"]:
            lines += [f"**Student**: {t['student']}" + (f"  _(earlier: {' / '.join(t['history'])})_" if t["history"] else ""), "",
                      f"**HYU Compass** ({t['action']}): " + t["assistant"].replace("\n", " "), ""]  # fmt: skip
    (OUT / "transcripts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    assert turn("reply_only", "Q", ["A", "B"]) == ("B", ["Q", "A"]) and turn("reply_reask", "Q", ["A"]) == ("Q", ["Q", "A"])
    assert reply_for("campus", {"campus": "seoul"}) == "I'm a Seoul campus student." and reply_for("year", {}) == "I'm not sure."
    assert score("abstain", {"right_referral": True}, True) == 2 and score("answer", {"facts": ["correct", "missing"], "wrong_group": False}, False) == 1
    cmd = sys.argv[1]
    raise SystemExit(asyncio.run(run()) if cmd == "run" else {"items": items, "compare": compare, "transcripts": transcripts}[cmd]())
