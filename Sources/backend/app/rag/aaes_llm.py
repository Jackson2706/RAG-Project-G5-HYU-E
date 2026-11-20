"""AAES+ (deck v4 Task 4): the LLM side of each AAES step. Prompts are fixed here; every reply is JSON only and is
validated before use. Anything invalid falls back to the rules for that item, and the fallback is counted.

    Step 1  PROFILE   -> parse_profile(raw, question, history)      {attribute: entry} (values in vocabulary v1, quote verified)
    Step 2  APPLIES   -> parse_applies(raw, passages, known)        {chunk_id: {"relevant", "label", "depends_on"}}
    Step 3  DIFFERS   -> parse_differs(raw, known)                  {"differs", "detail", "answers"} or None
            SAME      -> parse_same(raw)                           {"same", "difference"} or None (both mode only)
    Step 4  DECIDE    -> parse_decide(raw, known)                   {"action", "detail"} or None
            WORDING   -> check_wording(text, kind, options, campus) the LLM's ask / refer sentence, or None

Modes per step: rules (AAES today), llm, both (rules + LLM); see the blocks that call these.
"""

from __future__ import annotations

import json
import re

from app.rag.aaes import CAMPUS_SELF, CAMPUS_WORD, NAMES, SHOWN, _show, answer_key, distinct_answers
from app.rag.applicability import VOCABULARY
from app.rag.blocks.query_processing.query_understanding.self_query import INSTRUCTION as SELF_QUERY

MODES = ("rules", "llm", "both")
ATTRS = json.dumps({a: list(v) for a, v in VOCABULARY.items()})

PROFILE = (SELF_QUERY + " For each attribute you keep, give the exact words the student used as \"quote\" and whether they said it in "
           "the \"Now\" line (\"turn\": \"now\") or an \"Earlier\" line (\"turn\": \"earlier\"). Leave out hypotheticals (\"if I were a "
           "master's student\"), questions about other groups (\"what about ERICA students?\"), and anything not said about the student "
           "themself. Reply with one JSON object only: {\"<attribute>\": {\"value\": \"<value>\", \"quote\": \"<exact words>\", \"turn\": "
           "\"now\"}}; {} if nothing is stated.")  # fmt: skip
APPLIES = ("You check which official passages help a university student. You get the student's known details and up to 6 passages "
           "with ids. For each passage decide: is it relevant to the question (it talks about what the question asks), and who does it "
           "apply to: \"everyone\", \"this_student\" (it names a group the known details match), \"other_students\" (it names a group "
           "the known details rule out), or \"depends\" (it names groups, but a detail the student has not given decides it). For "
           "\"depends\" list the deciding attributes from " + ", ".join(VOCABULARY) + ". For \"other_students\" quote the exact words "
           "of the passage that name the group. Reply with JSON only: {\"passages\": [{\"id\": \"P1\", \"relevant\": true, \"applies\": "
           "\"everyone\", \"depends_on\": [], \"quote\": \"\"}]}")  # fmt: skip
DIFFERS = ("You read official passages and decide whether the answer to the student's question differs between student groups, for a "
           "detail the student has NOT given. Allowed details and values: " + ATTRS + ". If one unknown detail changes the answer, reply "
           "{\"differs\": true, \"detail\": \"<attribute>\", \"answers\": {\"<value>\": \"<answer in at most 12 words>\", ...}} with one "
           "entry per value the passages cover. If the answer is the same for every student (or the known details already decide it), "
           "reply {\"differs\": false, \"detail\": null, \"answers\": {}}. Use only the passages. JSON only.")  # fmt: skip
DECIDE = ("You decide how a university help assistant should reply. Options: \"answer\" (the passages answer it for this student), "
          "\"per_case\" (the answer differs by an unknown detail and the cases are few: answer each case), \"ask\" (one unknown detail "
          "changes the answer a lot or there are many cases: ask for it), \"refer\" (the passages do not answer it: send the student to "
          "the office). Allowed details: " + ", ".join(VOCABULARY) + ". Reply with JSON only: {\"action\": \"answer\", \"detail\": null, "
          "\"reason\": \"<at most 15 words>\"}")  # fmt: skip
ASK = ("Write ONE short question (at most 40 words) that asks the student for their {name}. Name exactly these options: {options}, and "
       "say in a few words what differs between them, using only the passages. End with a question mark. Reply with the question only.")
REFER = ("Write one or two short sentences (at most 40 words) telling the student that the official English pages do not answer this "
         "question and that they should contact {office}. Do not answer the question. Reply with the sentences only.")
EXTRACT = ("Answer the question using only the evidence, in at most 12 words (a number, a date, yes/no or a short phrase). "
           "If the evidence does not answer the question, reply NONE.")  # the A0b extraction prompt, unchanged
SAME = ("Decide whether all the supplied answers mean the same thing for the student's question. Ignore wording differences, "
        "but keep differences in eligibility, requirements, dates, amounts, and yes/no. Reply with JSON only: "
        "{\"same\": true, \"difference\": \"\"} if all agree, otherwise {\"same\": false, \"difference\": "
        "\"<what differs, at most 15 words>\"}.")

# Words that name an attribute in a passage (a conflict needs a quote that names one of the student's known attributes).
SURFACE = {"campus": ("seoul", "erica", "ansan"), "degree_level": ("undergraduate", "bachelor", "master", "doctoral", "ph.d", "phd", "graduate", "language"),
           "year": ("year", "freshman", "sophomore", "junior", "senior", "semester"), "student_type": ("exchange", "visiting", "degree", "language"),
           "visa": ("d-2", "d-4", "d-10", "visa"), "topik_level": ("topik", "korean proficiency"), "english_track": ("english", "korean"),
           "academic_status": ("enrolled", "leave", "graduat", "coursework", "admitted", "applicant", "applicat", "freshmen", "new student"),
           "korean_standard": ("korean language standard", "korean standard")}  # fmt: skip


def norm(text: str) -> str:
    """Lowercase, straight quotes, single spaces. "I’m  at ERICA" -> "i'm at erica"."""
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')).strip().lower()


def quoted(quote: str, text: str) -> bool:
    """A quote counts only if (after normalisation) it appears in the text it claims to quote."""
    q = norm(quote).strip(" .,!?\"'")
    return bool(q) and q in norm(text)


def rule_kind(text: str, quote: str) -> str:
    """Classify a current-turn rule quote: self, hypothetical, or mention. A hypothetical cue lasts to the sentence end.

    >>> rule_kind("If I were a master's student at ERICA, could I take TOPIK?", "ERICA")
    'hypothetical'
    >>> rule_kind("I'm a Seoul campus student.", "Seoul")
    'self'
    >>> rule_kind("What about ERICA students?", "ERICA")
    'mention'
    >>> rule_kind("Suppose I'm at Seoul. My campus is ERICA.", "ERICA")
    'self'
    """
    text, quote = norm(text), norm(quote).strip(" .,!?\"'")
    at = text.rfind(quote)
    if not quote or at < 0:
        return "mention"
    # Campus rules prefer the last self-pattern over a later bare campus mention.
    campus_hits = list(CAMPUS_SELF.finditer(text)) if CAMPUS_WORD.fullmatch(quote) else []
    if campus_hits:
        hit = campus_hits[-1]
        group = 1 if hit.group(1) else 2
        if hit.group(group) == quote:
            at = hit.start(group)
    start = max(text.rfind(mark, 0, at) for mark in ".?!") + 1
    prefix = text[start:at + len(quote)]
    if re.search(r"\b(?:if i (?:were|was)|suppose|imagine|what if|hypothetically|let's say)\b", prefix):
        return "hypothetical"
    if re.search(r"\b(?:i'm|i am|i study|my)\b", prefix):
        return "self"
    return "mention"


def load_json(raw: str):
    match = re.search(r"\{.*\}", raw or "", re.S)
    try:
        return json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None


def parse_profile(raw: str, question: str, history: list[str] | tuple) -> tuple[dict[str, tuple[str, str, str]], list[str]]:
    """({attribute: (value, status, quote)}, rejected items). turn now -> stated, earlier -> remembered.

    >>> parse_profile('{"campus": {"value": "erica", "quote": "at ERICA", "turn": "now"}}', "I'm at ERICA. Can I work?", [])[0]
    {'campus': ('erica', 'stated', 'at ERICA')}
    """
    data = load_json(raw)
    if not isinstance(data, dict):
        return {}, ["unparseable"]
    found, rejected = {}, []
    for attribute, entry in data.items():
        if not isinstance(entry, dict) or attribute not in VOCABULARY:
            rejected.append(f"{attribute}:shape")
            continue
        value, quote, turn = str(entry.get("value", "")).strip(), str(entry.get("quote", "")), entry.get("turn")
        texts = [question] if turn == "now" else list(history) if turn == "earlier" else []
        if value not in VOCABULARY[attribute]:
            rejected.append(f"{attribute}:value")
        elif not any(quoted(quote, t) for t in texts):
            rejected.append(f"{attribute}:quote")
        else:
            found[attribute] = (value, "stated" if turn == "now" else "remembered", quote)
    return found, rejected


LABEL = {"everyone": "unconditioned", "this_student": "compatible", "other_students": "conflicting", "depends": "open"}


def parse_applies(raw: str, passages: dict[str, str], known: dict[str, list[str]]) -> tuple[dict[str, dict], list[str]]:
    """{passage id: {"relevant", "label", "depends_on"}} for the ids asked about; invalid items are left out (rules decide them).

    other_students becomes "conflicting" only with a verified quote that names one of the student's known attributes; otherwise "open".
    """
    data = load_json(raw)
    items = data.get("passages") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}, ["unparseable"]
    out, rejected = {}, []
    for item in items:
        pid = str((item or {}).get("id", "")) if isinstance(item, dict) else ""
        applies = item.get("applies") if isinstance(item, dict) else None
        if pid not in passages or applies not in LABEL or not isinstance(item.get("relevant"), bool):
            rejected.append(f"{pid or '?'}:shape")
            continue
        label = LABEL[applies]
        if label == "conflicting":
            quote = str(item.get("quote", ""))
            names_known = any(w in norm(quote) for a in known for w in SURFACE.get(a, ()))
            if not (quoted(quote, passages[pid]) and names_known):
                rejected.append(f"{pid}:conflict_quote")
                continue
        depends = [a for a in item.get("depends_on") or [] if a in VOCABULARY and a not in known]
        out[pid] = {"relevant": item["relevant"], "label": label, "depends_on": depends}
    return out, rejected


def parse_differs(raw: str, known: dict[str, list[str]]) -> dict | None:
    """Valid only if the detail is in the vocabulary, unknown for the student, and there are >= 2 distinct answers.

    >>> parse_differs('{"differs": true, "detail": "campus", "answers": {"seoul": "20 hours", "erica": "30 hours on weekdays"}}', {})["detail"]
    'campus'
    """
    data = load_json(raw)
    if not isinstance(data, dict) or not isinstance(data.get("differs"), bool):
        return None
    if not data["differs"]:
        return {"differs": False, "detail": None, "answers": {}}
    detail, answers = data.get("detail"), data.get("answers")
    if detail not in VOCABULARY or detail in known or not isinstance(answers, dict):
        return None
    answers = {str(v): str(a)[:120] for v, a in answers.items() if str(v) in VOCABULARY[detail] and a}
    groups = distinct_answers([answer_key(a) for a in answers.values()])
    if len({g for g in groups if g >= 0}) < 2:
        return None
    return {"differs": True, "detail": detail, "answers": answers}


def parse_same(raw: str) -> dict | None:
    """A semantic comparison needs a JSON boolean and a difference of at most 15 words.

    >>> parse_same('{"same": true, "difference": ""}')
    {'same': True, 'difference': ''}
    >>> parse_same('{"same": "true", "difference": ""}') is None
    True
    """
    data = load_json(raw)
    if not isinstance(data, dict) or not isinstance(data.get("same"), bool):
        return None
    difference = data.get("difference")
    if not isinstance(difference, str) or len(difference.split()) > 15:
        return None
    return {"same": data["same"], "difference": difference.strip()}


ACTION = {"answer": "ANSWER", "per_case": "CONDITIONAL", "ask": "CLARIFY", "refer": "ABSTAIN"}


def parse_decide(raw: str, known: dict[str, list[str]]) -> dict | None:
    data = load_json(raw)
    if not isinstance(data, dict) or data.get("action") not in ACTION:
        return None
    detail = data.get("detail")
    detail = detail if detail in VOCABULARY and detail not in known else None
    if data["action"] == "ask" and detail is None:
        return None
    return {"action": ACTION[data["action"]], "detail": detail, "reason": str(data.get("reason", ""))[:120]}


def check_wording(text: str, kind: str, options: list[str], campus: str | None) -> str | None:
    """The LLM's ask / refer wording, or None (then the template is used).

    ask: a question naming at least two of the allowed options and no other value of that attribute.
    refer: names an office, and only the student's own campus when it is known.
    """
    t = (text or "").strip().strip('"')
    if not t or len(t.split()) > 60:
        return None
    low = norm(t)
    if kind == "ask":
        shown = {v: norm(SHOWN.get(v, v.replace("_", " "))) for v in options}
        named = [v for v, s in shown.items() if s in low]
        if not t.endswith("?") or len(named) < 2:
            return None
        return t
    if "office" not in low and "oia" not in low:
        return None
    if campus and (("erica" in low) if campus == "seoul" else ("seoul" in low)):
        return None
    return t


def office(profile: dict[str, dict]) -> str:
    campus = profile.get("campus", {}).get("values") or []
    return f"the {SHOWN[campus[0]]} campus OIA office" if len(campus) == 1 else "the OIA office of their campus"


def ask_prompt(attribute: str, options: list[str]) -> str:
    return ASK.format(name=NAMES[attribute], options=_show(options))


def passage_line(i: int, text: str, campus: list[str], who: str) -> str:
    return f"[P{i}] (campus: {', '.join(campus) or 'both'}; for: {who})\n{text[:1200]}"


async def call(block, system: str, user: str) -> str:
    """One LLM call of an AAES+ step with the block's model / temperature / max_tokens, seed 42, 4,096-token context.
    Counted in the block's trace details ("llm_calls"); the raw replies are kept there too (first 400 characters)."""
    ollama = block.services.ollama
    model = await ollama.pick_model(block.params.get("model", ""), block.services.settings.ollama_chat_model)
    options = {"temperature": block.params.get("temperature", 0.0), "num_predict": block.params.get("max_tokens", 256), "num_ctx": 4096, "seed": 42}
    text, _ = await ollama.complete(model, [{"role": "system", "content": system}, {"role": "user", "content": user}], options)
    details = block.trace_details
    details["llm_calls"] = details.get("llm_calls", 0) + 1
    details.setdefault("llm_raw", []).append(text[:400])
    details["model"] = model["name"]
    return text


def fallback(block, step: str, items: list[str]) -> None:
    """Count items where the LLM output was invalid and the rules decided instead."""
    if items:
        counts = block.trace_details.setdefault("fallbacks", {})
        counts[step] = counts.get(step, 0) + len(items)
        block.trace_details.setdefault("fallback_items", []).extend(f"{step}:{i}" for i in items)
