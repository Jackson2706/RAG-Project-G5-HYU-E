"""IMPLEMENTED — AAES steps 3 and 4: branches with information gain, then the action policy.

AAES+ (deck v4 Task 4) adds two modes, each rules (AAES today) | llm | both:
  step3_mode  which missing detail matters?
              llm  = one LLM call: {"differs", "detail", "answers"}; valid only if the detail is in the vocabulary, unknown
                     for the student, and there are >= 2 distinct answers; else the rules' branches are kept.
              both = the rules propose the branch table; the LLM writes a <= 12-word answer per branch evidence set (the
                     A0b EXTRACT prompt); every set answered with one distinct answer -> ANSWER. Multiple lexical groups
                     with matching numbers get one SAME comparison; semantic agreement -> ANSWER. A NONE (that group
                     is referred), differing numbers, disagreement or an invalid comparison keeps the rules' decision.
  step4_mode  decide and write.
              llm  = one LLM call picks answer / per_case / ask / refer; the writer then runs as today.
              both = the rules choose the action; for ask and refer the LLM writes the wording, checked to name only
                     allowed values (the right campus office); the template on failure.
Every invalid LLM output falls back to the rules and is counted in the trace details ("fallbacks").
"""

from __future__ import annotations

from app.rag import aaes_llm
from app.rag.aaes import NAMES, _show, answer_key, branch_note, decide, distinct_answers, extract_profile, known_values, render_action
from app.rag.applicability import VOCABULARY, ChunkCondition
from app.rag.blocks.evidence.evidence_sufficiency.base import BaseSufficiencyChecker
from app.rag.schemas import Evidence, SufficiencyDecision
from app.rag.text import query_coverage

UNTAGGED = ChunkCondition(campus=list(VOCABULARY["campus"])).to_dict()  # never used on a tagged index
MAX_EXTRACTIONS = 6  # step3 both: more branch evidence sets than this -> keep the rules' decision


class ApplicabilitySufficiency(BaseSufficiencyChecker):
    """Hyperparameters: relevance_threshold (query coverage a chunk needs to count as relevant), max_branches
    (more → CLARIFY), temporal (drop outdated support when a newer version exists; off = A6), policy
    ("aaes", "always_clarify" = A3, or "question_only" = A4), and the AAES+ step3_mode / step4_mode with the
    auxiliary LLM's settings.

    Proceeds (generation runs) for ANSWER and CONDITIONAL; CLARIFY, ABSTAIN and CONFIRM get a fixed reply.
    """

    async def check(self, question: str, evidence: list[Evidence], profile: dict | None = None) -> SufficiencyDecision:
        profile = profile or extract_profile(question)
        coverage, chunks = self.relevant_chunks(question, evidence)
        d = decide(chunks, profile, max_branches=self.params["max_branches"], temporal=self.params["temporal"], policy=self.params["policy"],
                     question=question)
        step3, step4 = self.params.get("step3_mode", "rules"), self.params.get("step4_mode", "rules")
        if step3 == step4 == "rules":
            return self.result(d, evidence, profile, coverage)
        note = None
        if step3 == "llm" and d["action"] not in ("ABSTAIN", "CONFIRM"):
            d, note = await self._llm_branches(question, evidence, profile, d)
        elif step3 == "both" and d["action"] in ("CONDITIONAL", "CLARIFY"):
            d = await self._extract_branches(question, evidence, d)
        if step4 == "llm" and d["action"] != "CONFIRM":
            d, note = await self._llm_decide(question, evidence, profile, d, note)
        message = None
        if step4 == "both" and d["action"] in ("CLARIFY", "ABSTAIN"):
            message = await self._llm_wording(evidence, profile, d)
        return self.result(d, evidence, profile, coverage, message=message, note=note)

    def relevant_chunks(self, question: str, evidence: list[Evidence]) -> tuple[dict[str, float], list[dict]]:
        """(query coverage per chunk, the relevant chunks in the form decide() reads).

        AAES+ step 2: relevance_mode llm -> the LLM's relevance flag (the overlap rule when it has none); both -> overlap or LLM.
        """
        coverage = {e.chunk_id: round(query_coverage(question, e.text), 4) for e in evidence}

        def relevant(e: Evidence) -> bool:
            overlap = coverage[e.chunk_id] >= self.params["relevance_threshold"]
            mode, llm = e.applicability.get("relevance_mode"), e.applicability.get("llm_relevant")
            if mode == "llm" and llm is not None:
                return llm
            return overlap or (mode == "both" and bool(llm))

        chunks = [{"id": e.chunk_id, "doc_id": e.doc_id, "condition": e.applicability.get("condition") or UNTAGGED,
                   "status": e.applicability.get("condition_status") or "unknown", "superseded": e.applicability.get("superseded", False),
                   "fixed_label": e.applicability.get("llm_label")}
                  for e in evidence if relevant(e)]  # fmt: skip
        return coverage, chunks

    def result(self, d: dict, evidence: list[Evidence], profile: dict, coverage: dict[str, float], message: str | None = None,
               note: str | None = None) -> SufficiencyDecision:
        action = d["action"]
        support = [e.chunk_id for e in evidence if e.chunk_id in set(d["support"])]
        proceed = action in ("ANSWER", "CONDITIONAL")
        if action == "CONDITIONAL" and note is None:
            note = branch_note(d, support)
        return SufficiencyDecision(sufficient=proceed, reason=f"{action}: {d['reason']}", action=action,
                                   signals={**d, "coverage": coverage, "relevance_threshold": self.params.get("relevance_threshold")},
                                   evidence_ids=support if proceed else None, message=None if proceed else message or render_action(d, profile),
                                   prompt_note=note if action == "CONDITIONAL" else None)  # fmt: skip

    # ------------------------------------------------------------------ AAES+ helpers

    def _evidence_block(self, evidence: list[Evidence], d: dict) -> str:
        names = {"compatible": "this student", "conflicting": "other students", "open": "depends on the student",
                 "unconditioned": "everyone", "unknown": "not stated"}  # fmt: skip
        lines = []
        for i, e in enumerate(evidence, 1):
            cond = e.applicability.get("condition") or {}
            label = d.get("labels", {}).get(e.chunk_id) or e.applicability.get("label") or "unknown"
            lines.append(aaes_llm.passage_line(i, e.text, cond.get("campus") or [], names.get(label, label)))
        return "\n\n".join(lines)

    def _student(self, profile: dict) -> str:
        return "; ".join(f"{a}: {', '.join(v)}" for a, v in known_values(profile).items()) or "nothing known"

    async def _llm_branches(self, question: str, evidence: list[Evidence], profile: dict, d: dict) -> tuple[dict, str | None]:
        user = f"Question: {question}\nKnown about the student: {self._student(profile)}\n\n{self._evidence_block(evidence, d)}"
        s3 = aaes_llm.parse_differs(await aaes_llm.call(self, aaes_llm.DIFFERS, user), known_values(profile))
        self.trace_details["step3_llm"] = s3
        if s3 is None:
            aaes_llm.fallback(self, "differs", ["invalid"])
            return d, None
        if not s3["differs"]:
            return {**d, "action": "ANSWER", "reason": "llm_no_difference", "branch_attributes": [], "clarify_attribute": None}, None
        detail, answers = s3["detail"], s3["answers"]
        d = {**d, "branch_attributes": [detail], "branches": {detail: {"ig": None, "outcomes": {v: [] for v in answers}}},
             "branch_table": [{"when": {detail: [v]}, "answer": a, "evidence": list(d["support"])} for v, a in answers.items()],
             "branch_answers": answers}  # fmt: skip
        if len(answers) > self.params["max_branches"]:
            return {**d, "action": "CLARIFY", "reason": "llm_many_branches", "clarify_attribute": detail}, None
        return {**d, "action": "CONDITIONAL", "reason": "llm_differs", "clarify_attribute": detail}, self._answers_note(detail, answers)

    def _answers_note(self, detail: str, answers: dict[str, str]) -> str:
        lines = [f"The answer depends on the student's {NAMES[detail]}. Answer every case below separately, starting each with "
                 "'If you'; do not pick one for the student. Use the evidence for the details and cite it."]  # fmt: skip
        lines += [f"- {NAMES[detail]} {_show([v])}: {a}" for v, a in answers.items()]
        return "\n".join(lines)

    async def _extract_branches(self, question: str, evidence: list[Evidence], d: dict) -> dict:
        texts = {e.chunk_id: e.text for e in evidence}
        sets = list(dict.fromkeys(tuple(row["evidence"]) for row in d["branch_table"] if row["evidence"]))
        if not sets or len(sets) > MAX_EXTRACTIONS:
            self.trace_details["extractions"] = f"skipped: {len(sets)} evidence sets"
            self.trace_details["same_check"] = "skipped: extraction_limit" if sets else "skipped: no_sets"
            return d
        values = []
        for ids in sets:
            block = "\n\n".join(texts[c][:1500] for c in ids if c in texts)
            values.append(await aaes_llm.call(self, aaes_llm.EXTRACT, f"Question: {question}\n\nEvidence:\n{block}"))
        keys = [answer_key(v) for v in values]
        groups = distinct_answers(keys)
        distinct = {g for g in groups if g >= 0}
        self.trace_details["extractions"] = [{"evidence": list(ids), "value": v[:120], "group": g} for ids, v, g in zip(sets, values, groups, strict=True)]
        if -1 in groups:
            self.trace_details["same_check"] = "skipped: unanswered_set"
            return d  # the group without an answer is referred; keep the split
        if len(distinct) == 1:
            self.trace_details["same_check"] = "skipped: same_answer"
            return {**d, "action": "ANSWER", "reason": "same_answer", "branch_attributes": [], "clarify_attribute": None}
        numbers = {frozenset(w for w in key if w.isdigit()) for key in keys if key is not None}
        if len(numbers) > 1:  # T39: numbers override any semantic comparison
            self.trace_details["same_check"] = "skipped: different_numbers"
            return d
        answers = "\n".join(f"[G{g + 1}] {values[groups.index(g)]}" for g in sorted(distinct))
        same = aaes_llm.parse_same(await aaes_llm.call(self, aaes_llm.SAME, f"Question: {question}\n\nAnswers:\n{answers}"))
        if same is None:
            self.trace_details["same_check"] = "skipped: invalid"
            aaes_llm.fallback(self, "same", ["invalid"])
            return d
        self.trace_details["same_check"] = {"groups": len(distinct), **same}
        if same["same"]:
            return {**d, "action": "ANSWER", "reason": "same_meaning", "branch_attributes": [], "clarify_attribute": None}
        return d

    async def _llm_decide(self, question: str, evidence: list[Evidence], profile: dict, d: dict, note: str | None) -> tuple[dict, str | None]:
        branches = (f"Step 3 found that the answer depends on: {', '.join(d['branch_attributes'])}" + (f" ({d['branch_answers']})" if d.get("branch_answers") else "")
                    if d.get("branch_attributes") else "Step 3 found no detail that changes the answer.")  # fmt: skip
        user = f"Question: {question}\nKnown about the student: {self._student(profile)}\n{branches}\n\n{self._evidence_block(evidence, d)}"
        choice = aaes_llm.parse_decide(await aaes_llm.call(self, aaes_llm.DECIDE, user), known_values(profile))
        self.trace_details["step4_llm"] = choice
        if choice is None:
            aaes_llm.fallback(self, "decide", ["invalid"])
            return d, note
        action, detail = choice["action"], choice["detail"]
        if action == "ABSTAIN":
            return {**d, "action": "ABSTAIN", "reason": "llm_refer"}, note
        if action == "CLARIFY":
            branches = d["branches"] if detail in d.get("branches", {}) else {**d.get("branches", {}), detail: {"ig": None, "outcomes": {v: [] for v in VOCABULARY[detail]}}}
            return {**d, "action": "CLARIFY", "reason": "llm_ask", "clarify_attribute": detail, "branches": branches}, note
        if action == "CONDITIONAL" and not d.get("branch_table"):
            aaes_llm.fallback(self, "decide", ["per_case_without_branches"])
            return {**d, "action": "ANSWER", "reason": "llm_per_case_no_branches"}, note
        return {**d, "action": action, "reason": f"llm_{action.lower()}"}, note

    async def _llm_wording(self, evidence: list[Evidence], profile: dict, d: dict) -> str | None:
        campus = profile.get("campus", {}).get("values") or []
        if d["action"] == "CLARIFY":
            attribute = d["clarify_attribute"]
            options = list(d["branches"].get(attribute, {}).get("outcomes") or VOCABULARY[attribute])
            system, kind = aaes_llm.ask_prompt(attribute, options), "ask"
        else:
            options, system, kind = [], aaes_llm.REFER.format(office=aaes_llm.office(profile)), "refer"
        text = await aaes_llm.call(self, system, self._evidence_block(evidence, d))
        checked = aaes_llm.check_wording(text, kind, options, campus[0] if len(campus) == 1 else None)
        if checked is None:
            aaes_llm.fallback(self, "wording", [kind])
        return checked
