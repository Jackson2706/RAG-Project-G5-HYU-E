"""AAES online steps 1–4 as pure functions (spec: docs/aaes_spec.md, "Online steps (P7)"; tests: test_aaes_t24.py).

The blocks (profile_understanding, applicability_reranker, applicability_sufficiency) only call these.

    Step 1  extract_profile(question, history, remembered) -> {attribute: {"values", "status", "evidence"}}
    Step 2  label_chunk(condition, condition_status, known) -> compatible | conflicting | open | unconditioned | unknown
            penalized_score(score, label, outdated, lam, mu)
    Step 3  information_gain(attribute, chunks, profile) -> (IG in bits, {value: [chunk ids that apply]})
    Step 4  decide(chunks, profile) -> {"action": ANSWER | CONDITIONAL | CLARIFY | ABSTAIN | CONFIRM, ...}
            render_action(decision, profile) for CLARIFY / ABSTAIN / CONFIRM; with_caveat(answer, decision)
"""

from __future__ import annotations

import math
import re
from itertools import product

from app.rag.applicability import FIT_COMPATIBLE, FIT_CONFLICTING, SCOPE_DEFAULTS, VOCABULARY, ChunkCondition, condition_fit

ACTIONS = ("ANSWER", "CONDITIONAL", "CLARIFY", "ABSTAIN", "CONFIRM")
UNKNOWN_CAVEAT = "This may depend on your situation; please confirm with the OIA office."
KNOWN_STATUSES = ("stated", "remembered", "stale")

# --------------------------------------------------------------------------- step 1: profile (rules, no LLM)

_I = re.IGNORECASE
CAMPUS_WORD = re.compile(r"\b(seoul|erica|ansan)\b", _I)
CAMPUS_SELF = re.compile(r"\bI(?:'m| am)\b[^.?!]{0,30}?\b(seoul|erica|ansan)\b|\b(seoul|erica|ansan)(?: campus)? student\b", _I)
VISA = re.compile(r"\b([DF])\s*-\s*(\d{1,2})(?:\s*-\s*(\d))?\b", _I)
# attribute -> [(pattern, value)]; the last match in a text wins (a later statement replaces an earlier one)
PATTERNS: dict[str, list[tuple[re.Pattern, str]]] = {
    "degree_level": [(re.compile(r"\b(?:undergrad\w*|bachelor'?s?)\b", _I), "undergraduate"),
                     (re.compile(r"\bmaster'?s?\b", _I), "master"),
                     (re.compile(r"\b(?:ph\.?d|doctoral|doctorate)\b", _I), "doctoral"),
                     (re.compile(r"\blanguage (?:program|course) student\b", _I), "language_program")],
    "year": [(re.compile(rf"\b(?:{w}[- ]year|year {n}|{n}(?:st|nd|rd|th)[- ]year|{s})\b", _I), n)
             for n, w, s in (("1", "first", "freshman"), ("2", "second", "sophomore"), ("3", "third", "junior"), ("4", "fourth", "senior"))],
    "student_type": [(re.compile(r"\bexchange student\b|\bon exchange\b", _I), "exchange"),
                     (re.compile(r"\bvisiting student\b", _I), "visiting"),
                     (re.compile(r"\bdegree[- ]seeking\b", _I), "degree_seeking"),
                     (re.compile(r"\blanguage (?:program|course) student\b", _I), "language_program")],
    "topik_level": [(re.compile(r"\btopik\s*(?:level\s*)?([1-6])\b", _I), r"\1"),
                    (re.compile(r"\b(?:no|without|don'?t have(?: a| any)?) topik\b", _I), "none")],
    "english_track": [(re.compile(r"\benglish[- ](?:track|taught)\b", _I), "yes"), (re.compile(r"\bkorean[- ]track\b", _I), "no")],
    "academic_status": [
        (re.compile(r"\bappl(?:y|ying|ication) (?:to|for) (?:the )?(?:admission|graduate school|hanyang|university|"
                    r"(?:master|doctoral|bachelor|ph\.?d)\S* (?:program|degree))|\badmission (?:requirements?|guide|process)\b|"
                    r"\b(?:applicant|prospective student)\b", _I), "applicant"),
        (re.compile(r"\bI (?:was|got|have been|'ve been) (?:admitted|accepted)\b", _I), "admitted_not_enrolled"),
        (re.compile(r"\bI(?:'m| am) (?:currently )?enrolled\b", _I), "enrolled"),
        (re.compile(r"\bon (?:a )?leave of absence\b|\bI(?:'m| am) on leave\b", _I), "leave_of_absence"),
        (re.compile(r"\b(?:completed|finished) (?:all )?(?:my |of my )?coursework\b", _I), "completed_coursework"),
        (re.compile(r"\bI(?:'m| am) graduating\b", _I), "graduating")],
    "korean_standard": [(re.compile(r"\b(?:failed|did not (?:meet|satisfy|pass)) the korean (?:language )?standard", _I), "fail"),
                        (re.compile(r"\b(?:passed|met|satisfied) the korean (?:language )?standard", _I), "pass"),
                        (re.compile(r"\bexempt\w* from the korean (?:language )?standard", _I), "exempt")],
}  # fmt: skip


def _visa_value(match: re.Match) -> str:
    kind, major, minor = match.group(1).upper(), match.group(2), match.group(3)
    code = f"{kind}-{major}" + (f"-{minor}" if minor else "")
    if code in VOCABULARY["visa"]:
        return code
    return f"{kind}-{major}" if f"{kind}-{major}" in VOCABULARY["visa"] else "other"  # D-10-1 -> D-10, F-* -> other


def _statements(text: str) -> dict[str, tuple[str, str]]:
    """{attribute: (value, quote)} stated in one text. shortcut: the last visa code mentioned wins, so
    "I hold D-4 and want to change to D-2" reads as D-2; upgrade to a tense check if dev shows errors."""
    found: dict[str, tuple[str, str]] = {}
    self_campus = list(CAMPUS_SELF.finditer(text))
    campuses = {m.group(1).lower().replace("ansan", "erica"): m.group(1) for m in CAMPUS_WORD.finditer(text)}
    if self_campus:
        word = next(g for g in self_campus[-1].groups() if g)
        found["campus"] = (word.lower().replace("ansan", "erica"), word)
    elif len(campuses) == 1:
        found["campus"] = next(iter(campuses.items()))
    visas = list(VISA.finditer(text))
    if visas:
        found["visa"] = (_visa_value(visas[-1]), visas[-1].group(0))
    for attribute, rules in PATTERNS.items():
        hits = [(m.start(), m.expand(value), m.group(0)) for pattern, value in rules for m in pattern.finditer(text)]
        if hits:
            _, value, quote = max(hits)
            found[attribute] = (value, quote)
    return found


def extract_profile(question: str, history: list[str] | tuple = (), remembered: dict | None = None) -> dict[str, dict]:
    """Step 1. Memory (remembered/stale) < earlier turns (remembered) < the question (stated); later wins."""
    profile = {a: {"values": [], "status": "missing", "evidence": ""} for a in VOCABULARY}
    for attribute, entry in (remembered or {}).items():
        profile[attribute] = {"values": list(entry["values"]), "status": entry.get("status", "remembered"), "evidence": entry.get("evidence", "")}
    for status, texts in (("remembered", list(history)), ("stated", [question])):
        for text in texts:
            for attribute, (value, quote) in _statements(text).items():
                profile[attribute] = {"values": [value], "status": status, "evidence": quote}
    for attribute, values in SCOPE_DEFAULTS.items():
        if profile[attribute]["status"] == "missing":
            profile[attribute] = {"values": list(values), "status": "scope_default", "evidence": ""}
    return profile


def known_values(profile: dict[str, dict]) -> dict[str, list[str]]:
    """The values condition_fit may use: stated, remembered and stale (not scope defaults, which it adds itself)."""
    return {a: list(e["values"]) for a, e in profile.items() if e["status"] in KNOWN_STATUSES and e["values"]}


# --------------------------------------------------------------------------- step 2: labels and the soft penalty


def label_chunk(condition: dict, condition_status: str | None, known: dict[str, list[str]]) -> str:
    """Step 2. "unknown" (A23) is never "unconditioned"; a conflict (campus included) always wins."""
    parsed = ChunkCondition.from_dict(condition)
    fit = condition_fit(parsed, known)
    if fit == FIT_CONFLICTING:
        return FIT_CONFLICTING
    if condition_status == "unknown":
        return "unknown"
    if fit == FIT_COMPATIBLE and not parsed.constraints and not parsed.any_of:
        return "unconditioned"
    return fit


def penalized_score(score: float, label: str, outdated: bool, lam: float, mu: float) -> float:
    """score − λ·[conflicting] − μ·[outdated]. >>> penalized_score(2.0, "conflicting", True, 1.5, 0.5) → 0.0"""
    return score - lam * (label == FIT_CONFLICTING) - mu * bool(outdated)


# --------------------------------------------------------------------------- step 3: branches and information gain


def _value_space(attribute: str, profile: dict[str, dict]) -> list[str]:
    entry = profile.get(attribute, {})
    return list(entry["values"]) if entry.get("status") == "scope_default" else list(VOCABULARY[attribute])


def _applying(chunks: list[dict], known: dict[str, list[str]]) -> list[str]:
    return [c["id"] for c in chunks if label_chunk(c["condition"], c.get("status"), known) != FIT_CONFLICTING]


def _entropy(outcomes: list) -> float:
    counts = [outcomes.count(o) for o in set(outcomes)]
    return sum(n / len(outcomes) * math.log2(len(outcomes) / n) for n in counts)


def information_gain(attribute: str, chunks: list[dict], profile: dict[str, dict]) -> tuple[float, dict[str, list[str]]]:
    """IG(a) = entropy (bits) of "which chunks apply" over the values of `a`, uniform prior.

    Two chunks for TOPIK 3–6 and none–2: 4 of 7 values give {A}, 3 give {B} → H(4/7, 3/7) ≈ 0.985.
    """
    known = known_values(profile)
    outcomes = {v: _applying(chunks, {**known, attribute: [v]}) for v in _value_space(attribute, profile)}
    return _entropy([tuple(ids) for ids in outcomes.values()]), outcomes


def _condition_attributes(chunks: list[dict]) -> set[str]:
    names = {"campus"}
    for c in chunks:
        names |= set(c["condition"].get("constraints", {}))
        names |= {a for group in c["condition"].get("any_of", []) for a in group}
    return names


# --------------------------------------------------------------------------- step 4: policy


def decide(chunks: list[dict], profile: dict[str, dict], max_branches: int = 3, temporal: bool = True, policy: str = "aaes") -> dict:
    """Step 4 over the RELEVANT selected chunks: ABSTAIN → CONFIRM → ANSWER → CONDITIONAL → CLARIFY (spec order)."""
    known = known_values(profile)
    labels = {c["id"]: label_chunk(c["condition"], c.get("status"), known) for c in chunks}
    support = [c for c in chunks if labels[c["id"]] != FIT_CONFLICTING]
    if temporal and any(not c.get("superseded") for c in support):
        support = [c for c in support if not c.get("superseded")]
    out = {"action": "ABSTAIN", "reason": "", "labels": labels, "support": [c["id"] for c in support], "branch_attributes": [],
           "branches": {}, "branch_table": [], "clarify_attribute": None, "confirm_attribute": None,
           "unknown_condition_evidence": any(labels[c["id"]] == "unknown" for c in support)}  # fmt: skip
    if not support:
        return {**out, "reason": "no_evidence" if not chunks else "not_applicable", "unknown_condition_evidence": False}

    order = list(VOCABULARY)
    for attribute in sorted(_condition_attributes(chunks), key=order.index):  # CONFIRM: would the stale value matter?
        if profile.get(attribute, {}).get("status") == "stale":
            unsure = {**profile, attribute: {"values": [], "status": "missing", "evidence": ""}}
            applying = _applying(chunks, known_values(unsure))
            if information_gain(attribute, [c for c in chunks if c["id"] in applying], unsure)[0] > 0:
                return {**out, "action": "CONFIRM", "reason": "stale_value", "confirm_attribute": attribute}

    unknown_attrs = [a for a in sorted(_condition_attributes(support), key=order.index) if a not in known]
    if policy == "always_clarify":  # A3: no information gain, any unknown condition attribute triggers a question
        constrained = [a for a in unknown_attrs if a != "campus" or any(len(c["condition"]["campus"]) == 1 for c in support)]
        if constrained:
            return {**out, "action": "CLARIFY", "reason": "always_clarify", "clarify_attribute": constrained[0]}
        return {**out, "action": "ANSWER", "reason": "no_branch"}

    for attribute in unknown_attrs:
        ig, outcomes = information_gain(attribute, support, profile)
        out["branches"][attribute] = {"ig": round(ig, 6), "outcomes": outcomes}
    branch_attrs = [a for a in unknown_attrs if out["branches"][a]["ig"] > 1e-9]
    out["branch_attributes"] = branch_attrs
    if not branch_attrs:
        return {**out, "action": "ANSWER", "reason": "no_branch"}

    joint: dict[tuple, dict[str, set]] = {}  # outcome -> {attribute: values that lead to it}
    for values in product(*(_value_space(a, profile) for a in branch_attrs)):
        ids = tuple(_applying(support, {**known, **{a: [v] for a, v in zip(branch_attrs, values, strict=True)}}))
        when = joint.setdefault(ids, {a: set() for a in branch_attrs})
        for a, v in zip(branch_attrs, values, strict=True):
            when[a].add(v)
    out["branch_table"] = [{"when": {a: [v for v in _value_space(a, profile) if v in vs] for a, vs in when.items()}, "evidence": list(ids)}
                           for ids, when in joint.items()]  # fmt: skip
    differing = set().union(*map(set, joint)) - set.intersection(*map(set, joint))
    docs = {c["doc_id"] for c in support if c["id"] in differing}
    best = max(branch_attrs, key=lambda a: out["branches"][a]["ig"])  # ties: vocabulary order (max keeps the first)
    if len(joint) > max_branches:
        return {**out, "action": "CLARIFY", "reason": "many_branches", "clarify_attribute": best}
    if len(docs) > 1:
        return {**out, "action": "CLARIFY", "reason": "different_procedures", "clarify_attribute": best}
    return {**out, "action": "CONDITIONAL", "reason": "few_branches"}


# --------------------------------------------------------------------------- templates (no LLM)

NAMES = {"campus": "campus", "degree_level": "degree level", "year": "year of study", "student_type": "student type",
         "visa": "visa", "topik_level": "TOPIK level", "english_track": "track (English or Korean)",
         "academic_status": "academic status", "korean_standard": "Korean language standard result"}  # fmt: skip
SHOWN = {"seoul": "Seoul", "erica": "ERICA", "none": "no TOPIK", "yes": "English track", "no": "Korean track"}


def _show(values: list[str]) -> str:
    shown = [SHOWN.get(v, v.replace("_", " ")) for v in values]
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " or " + shown[-1]


def render_action(decision: dict, profile: dict[str, dict]) -> str:
    """The fixed reply for CLARIFY, ABSTAIN and CONFIRM (exactly one question for CLARIFY and CONFIRM)."""
    campus = profile.get("campus", {}).get("values") or []
    office = f"the {SHOWN[campus[0]]} campus OIA office" if len(campus) == 1 else "the OIA office of your campus"
    action = decision["action"]
    if action == "ABSTAIN":
        if decision["reason"] == "not_applicable":
            return f"The official pages I found do not apply to you (they are for another campus or student group). Please contact {office}."
        return f"I could not find this in the official English HYU pages. Please contact {office}."
    if action == "CLARIFY":
        attribute = decision["clarify_attribute"]
        options = decision["branches"].get(attribute, {}).get("outcomes") or {v: None for v in VOCABULARY[attribute]}
        return f"The answer depends on your {NAMES[attribute]}. Which applies to you: {_show(list(options))}?"
    if action == "CONFIRM":
        attribute = decision["confirm_attribute"]
        return f"Earlier you said your {NAMES[attribute]} is {_show(profile[attribute]['values'])}. Is that still correct?"
    raise ValueError(f"{action} is answered by the generator, not by a template")


def with_caveat(answer: str, decision: dict) -> str:
    """A23: append the unknown-condition caveat when an answer relies on a chunk with unknown status."""
    if decision.get("unknown_condition_evidence") and decision["action"] in ("ANSWER", "CONDITIONAL"):
        return f"{answer.rstrip()}\n\n{UNKNOWN_CAVEAT}"
    return answer


def branch_note(decision: dict, evidence_ids: list[str]) -> str:
    """CONDITIONAL: one line per branch for the prompt; evidence labels are E1.. in `evidence_ids` order."""
    label = {cid: f"[E{i}]" for i, cid in enumerate(evidence_ids, start=1)}
    lines = [f"The answer depends on the student's {' and '.join(NAMES[a] for a in decision['branch_attributes'])}. "
             "Answer every case below separately, starting each with 'If you'; do not pick one for the student."]  # fmt: skip
    for row in decision["branch_table"]:
        when = "; ".join(f"{NAMES[a]} {_show(values)}" for a, values in row["when"].items())
        use = "".join(label[c] for c in row["evidence"] if c in label) or "no evidence: say the student should ask the OIA office"
        lines.append(f"- {when}: use {use}")
    return "\n".join(lines)
