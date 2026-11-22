"""IMPLEMENTED — AG "AAES guard" (amendment A35 Step 3). The base pipeline (R16) answers as usual; the guard replaces
that only when ALL five checks hold. When it does not fire, the decision is a pass-through (no action, all selected
evidence, no note), so the reply is exactly the base pipeline's.

1. An unstated vocabulary attribute splits the selected evidence into >= 2 non-empty branches (aaes.decide's table).
2. Campus counts only if both campuses have campus-scoped evidence (a national rule applies to both values anyway).
3. Each branch separately: one yes/no call "does this evidence answer the question for a student with <a = v>?";
   "no" branches are dropped, empty branches never count.
4. The kept branches have different answer values (one short extraction per branch, aaes.same_answer: numbers,
   amounts, dates, levels and yes/no must match exactly, otherwise word sets).
5. One verification call quotes the differing text of two branches; both quotes must be found in their evidence
   (normalized as in the tag post-check). Otherwise no fire.
Fire: <= 2 kept branches -> CONDITIONAL with the branch note; > 2 -> CLARIFY on the attribute with the highest gain.
Every check is logged in signals["guard"] (Execution tab). No thresholds were tuned; temperature 0, seed 42, no thinking.
"""

from __future__ import annotations

import json
import re

from app.rag.aaes import NAMES, _show, answer_parts, both_campuses_scoped, decide, extract_profile, same_answer
from app.rag.blocks.evidence.evidence_sufficiency.applicability_sufficiency import UNTAGGED, ApplicabilitySufficiency
from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import _normalized_substring
from app.rag.schemas import Evidence, SufficiencyDecision

PROMPTS = {
    "branch_answers": "Does the evidence answer the question for a student with {extra}? Reply with yes or no only.",
    "extract": ("Answer the question for a student with {extra}, using only the evidence, in at most 12 words "
                "(a number, an amount, a date, yes/no or a short phrase). If the evidence does not answer it, reply NONE."),
    "verify": ("Two evidence sets, A and B, may give different answers to the question. {extra} Quote, word for word, the "
               "shortest part of A and of B that differs. Reply with JSON only: {{\"a\": \"<quote from A>\", \"b\": \"<quote from B>\"}}"),
}  # fmt: skip


class AAESGuard(ApplicabilitySufficiency):
    """Hyperparameters: model, temperature, max_tokens of the guard's yes/no, extraction and verification calls."""

    async def check(self, question: str, evidence: list[Evidence], profile: dict | None = None) -> SufficiencyDecision:
        profile = profile or extract_profile(question)
        log: dict = {"fired": False, "stop": None, "branches": []}

        def no_fire(stop: str) -> SufficiencyDecision:
            log["stop"] = stop
            return SufficiencyDecision(sufficient=True, reason=f"guard did not fire ({stop}): base reply", signals={"guard": log})

        chunks = [{"id": e.chunk_id, "doc_id": e.doc_id, "condition": e.applicability.get("condition") or UNTAGGED,
                   "status": e.applicability.get("condition_status") or "unknown", "superseded": e.applicability.get("superseded", False)}
                  for e in evidence]  # fmt: skip
        if not chunks:
            return no_fire("no_evidence")
        support = [c for c in chunks if c["id"] in set(decide(chunks, profile)["support"])]
        log["campus_candidate"] = both_campuses_scoped(support)  # check 2
        d = decide(chunks, profile, exclude=frozenset() if log["campus_candidate"] else frozenset({"campus"}))
        rows = [r for r in d["branch_table"] if r["evidence"]]  # check 1: non-empty branches only
        log["branch_attributes"] = d["branch_attributes"]
        if len(rows) < 2:
            return no_fire("no_split")

        texts = {e.chunk_id: e.text for e in evidence}
        kept = []
        for row in rows:  # check 3, then 4
            when = "; ".join(f"{NAMES[a]} = {_show(v)}" for a, v in row["when"].items())
            answers = (await self._ask("branch_answers", question, row["evidence"], when, texts)).strip().lower().startswith("yes")
            entry = {"when": row["when"], "evidence": row["evidence"], "answers": answers}
            if answers:
                entry["value"] = (await self._ask("extract", question, row["evidence"], when, texts)).strip()[:160]
                kept.append((row, answer_parts(entry["value"]), when))
            log["branches"].append(entry)
        kept = [k for k in kept if k[1] is not None]
        if len(kept) < 2:
            return no_fire("fewer_than_two_answering_branches")
        first = kept[0]
        other = next((k for k in kept[1:] if not same_answer(first[1], k[1])), None)
        if other is None:
            return no_fire("same_answer")

        def block(row):
            return "\n\n".join(texts[c] for c in row["evidence"] if c in texts)

        extra = f"A is for {first[2]}; B is for {other[2]}.\n\nA:\n{block(first[0])[:1500]}\n\nB:\n{block(other[0])[:1500]}"
        raw = await self._ask("verify", question, [], extra, texts)
        match = re.search(r"\{.*\}", raw, re.S)
        try:
            quotes = json.loads(match.group(0)) if match else {}
        except json.JSONDecodeError:
            quotes = {}
        quote_a, quote_b = str(quotes.get("a") or ""), str(quotes.get("b") or "")
        log["quotes"] = {"a": quote_a[:200], "b": quote_b[:200]}  # check 5
        if not (_normalized_substring(block(first[0]), quote_a) and _normalized_substring(block(other[0]), quote_b)):
            return no_fire("quotes_not_verified")

        log["fired"] = True
        used = list(dict.fromkeys(c for row, _, _ in kept for c in row["evidence"]))
        if len(kept) <= 2:
            fired = {**d, "action": "CONDITIONAL", "reason": "guard_conditional", "support": used, "branch_table": [k[0] for k in kept]}
        else:
            best = max(d["branch_attributes"], key=lambda a: d["branches"][a]["ig"])
            fired = {**d, "action": "CLARIFY", "reason": "guard_clarify", "clarify_attribute": best}
        decision = self.result(fired, evidence, profile, {})
        decision.signals["guard"] = log
        return decision

    async def _ask(self, kind: str, question: str, chunk_ids: list[str], extra: str, texts: dict[str, str]) -> str:
        ollama = self.services.ollama
        model = await ollama.pick_model(self.params["model"], self.services.settings.ollama_chat_model)
        evidence = "\n\n".join(texts[c][:1500] for c in chunk_ids if c in texts)
        user = f"Question: {question}" + (f"\n\nEvidence:\n{evidence}" if evidence else "")
        messages = [{"role": "system", "content": PROMPTS[kind].format(extra=extra)}, {"role": "user", "content": user}]
        options = {"temperature": self.params["temperature"], "num_predict": self.params["max_tokens"], "num_ctx": 4096, "seed": 42}
        text, _ = await ollama.complete(model, messages, options)
        return text
