"""Evaluator v2 (amendment A34): the action a student actually sees, read from the final reply text.

Evaluator v1 (metrics/aaes.label_action) maps a preset without an AAES action to answer/abstain from the generation
outcome, so a baseline can never be scored conditional_answer or clarify even when its reply is one. v2 classifies
the final reply of every preset (AAES templates included) the same way:

    conditional_answer  the reply gives >= 2 cases conditioned on student attributes (campus, degree, visa, ...)
    clarify             the reply asks the student something and gives no final answer
    abstain             the reply gives no answer from the sources and refers the student elsewhere
    answer              anything else

Rules decide the clear cases (the fixed AAES and refusal templates); qwen3.5:4b (temperature 0, seed 42, thinking
off, the fixed PROMPT below, hash in PROMPT_HASH) decides the rest. Rules and prompt were written on DEV outputs only
and frozen before any test output was classified. Labels are cached per (preset, qid) in <run>/reply_actions_v2.jsonl.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import httpx

VERSION = "v2"
LABELS = ("answer", "conditional_answer", "clarify", "abstain")
MODEL = {"model": "qwen3.5:4b", "temperature": 0.0, "seed": 42, "think": False, "num_ctx": 4096}
MAX_CHARS = 3000  # longer replies are cut; the action shows in the first part

# (pattern at the start of the reply, label). The AAES templates (app/rag/aaes.render_action) and the generator's
# insufficient-context reply (app/rag/schemas.py) are fixed strings, so they need no model.
RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"The answer depends on your [^.]+\. Which applies to you: [^?]+\?\s*$"), "clarify"),
    (re.compile(r"Earlier you said your [^.]+\. Is that still correct\?\s*$"), "clarify"),
    (re.compile(r"I could not find this in the official English HYU pages\. Please contact"), "abstain"),
    (re.compile(r"The official pages I found do not apply to you"), "abstain"),
    (re.compile(r"I could not find enough information in the indexed HYU documents to answer this question\."), "abstain"),
]

PROMPT = """You classify the reply a university help assistant gave to a student. Read only the reply and pick exactly one label.

conditional_answer: the reply gives at least two different answers for different kinds of students, each tied to a student attribute such as campus (Seoul or ERICA), degree level, visa type, TOPIK level, year, student type or academic status (for example "If you are at Seoul ... If you are at ERICA ...").
clarify: the reply asks the student a question about themselves (for example which campus or degree) and does not give a final answer.
abstain: the reply does not answer the question from the sources; it says the information was not found or does not apply, and may refer the student to an office or website. A reply that only explains what is missing is abstain.
answer: the reply gives one answer (it may add general advice or a short caveat). Use answer for anything else.

If a reply answers part of the question and then says the rest is missing, use answer. If a reply gives one answer and only mentions that rules may differ, use answer.

Reply:
<<<
{reply}
>>>

Output only the label: answer, conditional_answer, clarify or abstain."""
PROMPT_HASH = hashlib.sha256(PROMPT.encode()).hexdigest()[:12]


# >= 2 lines that open with "If you are ..." (bullets and bold allowed): cases per student attribute. Added on dev, where
# the model called such AAES CONDITIONAL replies "answer" (dev T14-058, T14-109). It applies to every preset alike.
CASE_LINE = re.compile(r"^[\s*\-•>#]*(?:\*\*)?If you are\b", re.M)


def rule_label(reply: str) -> str | None:
    """The label of a fixed template or of a reply with >= 2 "If you are" case lines, else None.

    "The answer depends on your campus. Which applies to you: Seoul or ERICA?" -> "clarify";
    "If you are at Seoul, ...\\nIf you are at ERICA, ..." -> "conditional_answer"; "Yes, you can." -> None.
    """
    text = reply.strip()
    label = next((label for pattern, label in RULES if pattern.match(text)), None)
    if label is None and len(CASE_LINE.findall(text)) >= 2:
        return "conditional_answer"
    return label


def parse_label(raw: str) -> str | None:
    """The model's word -> a label. "conditional_answer" -> "conditional_answer"; "Clarify." -> "clarify"; "" -> None."""
    match = re.search(r"conditional_answer|clarify|abstain|answer", raw.lower())  # the first label word wins
    return match.group(0) if match else None


def llm_label(reply: str, client: httpx.Client) -> tuple[str, str]:
    """(label, raw model output) for a reply no rule decides. An unparseable output counts as "answer" (the "else" class)."""
    body = {"model": MODEL["model"], "stream": False, "think": MODEL["think"],
            "options": {"temperature": MODEL["temperature"], "seed": MODEL["seed"], "num_ctx": MODEL["num_ctx"]},
            "messages": [{"role": "user", "content": PROMPT.format(reply=reply.strip()[:MAX_CHARS])}]}  # fmt: skip
    raw = client.post("/api/chat", json=body).raise_for_status().json()["message"]["content"]
    return parse_label(raw) or "answer", raw


def reply_sha(reply: str) -> str:
    return hashlib.sha256(reply.encode()).hexdigest()[:16]


def classify_folder(folder: Path, cache_path: Path, base_url: str = "http://localhost:11434", log=print) -> dict[tuple[str, str], str]:
    """Label the latest completed reply of every (preset, qid) in raw/hyu/<split>/; reuses cached labels of the same reply."""
    cache = {}
    if cache_path.exists():
        cache = {(r["preset"], r["qid"], r["reply_sha"]): r for r in map(json.loads, cache_path.read_text().splitlines())}
    by_reply = {r["reply_sha"]: r for r in cache.values()}  # identical replies (e.g. A0 and A6) are classified once
    labels = {}
    with httpx.Client(base_url=base_url, timeout=180.0) as client, cache_path.open("a", encoding="utf-8") as out:
        for path in sorted(folder.glob("*__-.jsonl")):
            preset = path.name.removesuffix("__-.jsonl")
            latest = {}
            for line in path.read_text().splitlines():
                rec = json.loads(line)
                if rec.get("status") == "completed":
                    latest[rec["qid"]] = rec
            for qid, rec in sorted(latest.items()):
                reply, sha = rec.get("answer") or "", reply_sha(rec.get("answer") or "")
                hit = cache.get((preset, qid, sha))
                if not hit:
                    same = by_reply.get(sha)
                    if same:
                        label, by, raw = same["label"], same["by"], same.get("raw", "")
                    elif (label := rule_label(reply)) is not None:
                        by, raw = "rule", ""
                    else:
                        label, raw = llm_label(reply, client)
                        by = "llm"
                    hit = {"preset": preset, "qid": qid, "reply_sha": sha, "label": label, "by": by, "raw": raw[:80],
                           "evaluator": VERSION, "prompt_hash": PROMPT_HASH}  # fmt: skip
                    out.write(json.dumps(hit) + "\n")
                    out.flush()
                    cache[(preset, qid, sha)] = by_reply[sha] = hit
                labels[(preset, qid)] = hit["label"]
            log(f"{preset}: {len(latest)} replies labelled")
    return labels
