"""Follow-up resolution (deck v6): after an AAES clarifying question, a detail-only reply answers the earlier question.

The backend marks every AAES CLARIFY reply with `clarify_marker` (trace["clarify"]); the client sends that marker back
with the next message. `resolve` decides whether the new message only gives the asked detail. If so, the effective
question is the question before the clarifying turn and the detail becomes a *stated* attribute (it overrides remembered
values); Steps 1-4 and the writer run unchanged. Behind the `followup_resolution` flag: on in the app (settings),
off in run_rag's default, so every frozen evaluation run is unchanged unless the run sets it.
"""

from __future__ import annotations

import re

from app.rag.aaes import SHOWN, extract_profile
from app.rag.applicability import VOCABULARY

QUESTION_WORDS = {"how", "what", "when", "where", "which", "who", "why", "can", "could", "do", "does", "is", "are", "should", "may", "will",
                  "tell", "explain", "show", "give", "list", "describe"}  # imperative openers ask for something new too
ALIASES = {"ansan": "erica"}
GRADUATE = ("master", "doctoral")


def clarify_options(decision: dict) -> list[str]:
    """The values a CLARIFY reply offers (the same list render_action shows)."""
    attribute = decision["clarify_attribute"]
    return list(decision.get("branches", {}).get(attribute, {}).get("outcomes") or VOCABULARY[attribute])


def clarify_marker(question: str, decision: dict, stated: dict[str, str] | None = None) -> dict:
    """`stated`: details already resolved in this follow-up, carried to the next reply (bare answers like "3" are not in history)."""
    return {"question": question, "attribute": decision["clarify_attribute"], "options": clarify_options(decision), "stated": dict(stated or {})}


def _option_match(message: str, options: list[str]) -> str | None:
    """The one offered option the message names (case-insensitive; Ansan = ERICA; grad/graduate only if unique)."""
    text = message.lower()
    words = set(re.findall(r"[a-z0-9'-]+", text))
    hits = {ALIASES[w] for w in words if w in ALIASES} & set(options)
    for v in options:
        names = {v.lower(), v.replace("_", " ").lower(), v.replace("_", "-").lower(), SHOWN.get(v, v).lower()}  # non_degree = "non-degree"
        if any(re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", text) for n in names):
            hits.add(v)
    if words & {"grad", "graduate"} and len(grad := [o for o in options if o in GRADUATE]) == 1:
        hits.add(grad[0])
    return hits.pop() if len(hits) == 1 else None


def resolve(message: str, marker: dict | None) -> dict | None:
    """{"question": earlier question, "stated": {attribute: value}} if `message` is a detail-only reply, else None."""
    if not marker or not marker.get("question"):
        return None
    words = message.split()
    if "?" in message or not words or len(words) > 20 or words[0].lower().strip(",.!") in QUESTION_WORDS:
        return None
    stated = {a: e["values"][0] for a, e in extract_profile(message).items() if e["status"] == "stated" and e["values"]}
    attribute = marker.get("attribute")
    if attribute not in stated and (value := _option_match(message, marker.get("options") or [])):
        stated[attribute] = value
    if not stated:
        return None
    earlier = {a: v for a, v in (marker.get("stated") or {}).items() if a in VOCABULARY and v in VOCABULARY[a]}
    return {"question": marker["question"], "reply": message, "stated": {**earlier, **stated}}


def apply_stated(profile: dict[str, dict], resolved: dict) -> dict[str, dict]:
    """The reply's details become stated attributes (they override remembered values)."""
    return {**profile, **{a: {"values": [v], "status": "stated", "evidence": resolved["reply"]} for a, v in resolved["stated"].items()}}
