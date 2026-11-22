"""IMPLEMENTED — AAES step 1: the student's profile from the question and the earlier turns.

mode (AAES+, deck v4 Task 4): rules = extract_profile (AAES today, no LLM); llm = one LLM call returning each stated
attribute with a quote that must appear in the turn it claims; both = self-statements and remembered rules win,
current hypothetical/mentioned rule values need matching LLM confirmation, and the LLM fills other missing attributes.
Invalid LLM items keep only self/remembered rules in both mode; llm mode keeps its existing rule fallback.
"""

from __future__ import annotations

from app.rag import aaes_llm
from app.rag.aaes import extract_profile
from app.rag.applicability import SCOPE_DEFAULTS
from app.rag.blocks.query_processing.query_understanding.base import BaseQueryUnderstanding
from app.rag.schemas import QueryAnalysis


class ProfileUnderstanding(BaseQueryUnderstanding):
    """Each vocabulary attribute gets values and a status: stated, remembered (an earlier turn), stale,
    scope_default (not an applicant unless said, A17) or missing. Nothing is guessed (aaes_spec.md, step 1).
    Hyperparameters: mode (rules, llm, both) and, for llm/both, the auxiliary LLM's model, temperature, max_tokens."""

    async def analyze(self, question: str, history: list[str] | tuple = ()) -> QueryAnalysis:
        rules = extract_profile(question, history)
        mode = self.params.get("mode", "rules")
        if mode == "rules":
            return QueryAnalysis(profile=rules)
        said = "\n".join([*(f"Earlier: {t}" for t in history), f"Now: {question}"])
        found, rejected = aaes_llm.parse_profile(await aaes_llm.call(self, aaes_llm.PROFILE, said), question, history)
        aaes_llm.fallback(self, "profile", rejected)
        if "unparseable" in rejected and mode == "llm":  # llm mode keeps its whole-profile rule fallback
            return QueryAnalysis(profile=rules)
        missing = {"values": [], "status": "missing", "evidence": ""}
        dropped = set()
        if mode == "both":
            self.trace_details["dropped_unconfirmed"] = []
            for attribute, entry in rules.items():
                if entry["status"] != "stated":
                    continue
                kind = aaes_llm.rule_kind(question, entry["evidence"])
                confirmation = found.get(attribute)
                if kind != "self" and (confirmation is None or confirmation[0] not in entry["values"]):
                    self.trace_details["dropped_unconfirmed"].append({"attribute": attribute, "value": entry["values"][0], "kind": kind})
                    rules[attribute] = dict(missing)
                    dropped.add(attribute)
        known = {a for a, e in rules.items() if e["status"] in ("stated", "remembered", "stale")}
        bad = {r.split(":")[0] for r in rejected}
        if mode == "llm":  # the LLM's reading; the rules only for attributes whose LLM item was invalid
            profile = {a: rules[a] if a in bad and a in known else dict(missing) for a in rules}
            fill = found
        else:  # both: a rejected current rule value stays missing even if the LLM proposed a different value
            profile = {a: e if a in known else dict(missing) for a, e in rules.items()}
            fill = {a: v for a, v in found.items() if a not in known and a not in dropped}
        for attribute, (value, status, quote) in fill.items():
            profile[attribute] = {"values": [value], "status": status, "evidence": quote}
        for attribute, values in SCOPE_DEFAULTS.items():
            if profile[attribute]["status"] == "missing":
                profile[attribute] = {"values": list(values), "status": "scope_default", "evidence": ""}
        self.trace_details["added_by_llm"] = sorted(fill)
        return QueryAnalysis(profile=profile)
