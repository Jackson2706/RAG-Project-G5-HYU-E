"""IMPLEMENTED — A0b "AAES spec-fixed" (amendment A34, exploratory, dev only): A0's steps 3-4 with three changes.

1. Branch only on distinct non-empty answer values: one short LLM extraction per distinct evidence set of the branch
   table (at most max_branches), compared with aaes.distinct_answers. 0 values -> ABSTAIN, 1 -> ANSWER, >= 2 -> CONDITIONAL.
2. The campus is a branch candidate only if the support has campus-scoped chunks for both campuses.
3. Before any CLARIFY (more evidence sets than max_branches), one yes/no sufficiency check; "no" -> ABSTAIN.
A0 (applicability_sufficiency) is unchanged.
"""

from __future__ import annotations

from app.rag.aaes import answer_key, both_campuses_scoped, decide, distinct_answers, extract_profile
from app.rag.blocks.evidence.evidence_sufficiency.applicability_sufficiency import ApplicabilitySufficiency
from app.rag.schemas import Evidence, SufficiencyDecision

EXTRACT = ("Answer the question using only the evidence, in at most 12 words (a number, a date, yes/no or a short phrase). "
           "If the evidence does not answer the question, reply NONE.")  # fmt: skip
SUFFICIENT = "Does the evidence answer the question, at least for some students? Reply with yes or no only."


class SpecFixedApplicabilitySufficiency(ApplicabilitySufficiency):
    """Hyperparameters: A0's (relevance_threshold, max_branches, temporal) plus model, temperature, max_tokens of the
    extraction calls. Every extraction is in the trace details."""

    async def check(self, question: str, evidence: list[Evidence], profile: dict | None = None) -> SufficiencyDecision:
        profile = profile or extract_profile(question)
        coverage, chunks = self.relevant_chunks(question, evidence)
        args = {"max_branches": self.params["max_branches"], "temporal": self.params["temporal"], "question": question}
        d = decide(chunks, profile, **args)
        support = [c for c in chunks if c["id"] in set(d["support"])]
        campus_ok = both_campuses_scoped(support)
        if not campus_ok:
            d = decide(chunks, profile, exclude=frozenset({"campus"}), **args)
        self.trace_details = {"campus_candidate": campus_ok, "a0_action": d["action"], "extractions": [], "sufficiency_check": None}
        if d["action"] not in ("CONDITIONAL", "CLARIFY"):
            return self.result(d, evidence, profile, coverage)

        texts = {e.chunk_id: e.text for e in evidence}
        sets = list(dict.fromkeys(tuple(row["evidence"]) for row in d["branch_table"] if row["evidence"]))
        if len(sets) > self.params["max_branches"]:  # too many to extract: ask, but only if the evidence answers at all
            reply = await self._ask(SUFFICIENT, question, [c for ids in sets for c in ids], texts)
            self.trace_details["sufficiency_check"] = reply[:40]
            if not reply.strip().lower().startswith("yes"):
                return self.result({**d, "action": "ABSTAIN", "reason": "insufficient"}, evidence, profile, coverage)
            return self.result({**d, "reason": "many_branches"}, evidence, profile, coverage)

        values = [await self._ask(EXTRACT, question, list(ids), texts) for ids in sets]
        group = dict(zip(sets, distinct_answers([answer_key(v) for v in values]), strict=True))
        self.trace_details["extractions"] = [{"evidence": list(ids), "value": v[:120], "group": group[ids]} for ids, v in zip(sets, values, strict=True)]
        answering = [row for row in d["branch_table"] if row["evidence"] and group[tuple(row["evidence"])] >= 0]
        distinct = {group[tuple(row["evidence"])] for row in answering}
        if not distinct:
            return self.result({**d, "action": "ABSTAIN", "reason": "no_answer"}, evidence, profile, coverage)
        used = list(dict.fromkeys(c for row in answering for c in row["evidence"]))
        if len(distinct) == 1:
            return self.result({**d, "action": "ANSWER", "reason": "same_answer", "support": used}, evidence, profile, coverage)
        return self.result({**d, "action": "CONDITIONAL", "reason": "distinct_answers", "support": used, "branch_table": answering},
                           evidence, profile, coverage)  # fmt: skip

    async def _ask(self, instruction: str, question: str, chunk_ids: list[str], texts: dict[str, str]) -> str:
        ollama = self.services.ollama
        model = await ollama.pick_model(self.params["model"], self.services.settings.ollama_chat_model)
        block = "\n\n".join(texts[c][:1500] for c in chunk_ids if c in texts)
        messages = [{"role": "system", "content": instruction}, {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{block}"}]
        options = {"temperature": self.params["temperature"], "num_predict": self.params["max_tokens"], "num_ctx": 4096, "seed": 42}
        text, _ = await ollama.complete(model, messages, options)
        return text
