# T42 — AAES+ "both" mode: Step 1 bare/hypothetical values, Step 3 grouping by meaning
Owner: Codex (gpt-6.1-sol) · Reviewer: Claude Code · Phase: deck v5 Phase 1

Goal: fix two measured dev failures of the AAES+ "both" modes without changing AAES (rules mode, RRRR = A0) or the
"llm" modes. (1) Hypothetical identity: "If I were a master's student at ERICA…" makes the rules record ERICA/master
as the student's own. (2) Winter school (dev T14-042): branch answers that say the same thing in different words are
split, so AAES+ asks an unneeded campus question.

Read first: AGENTS.md; Sources/backend/app/rag/aaes_llm.py; Sources/backend/app/rag/aaes.py (`_statements`,
CAMPUS_SELF, CAMPUS_WORD, `extract_profile`, `answer_key`, `distinct_answers`);
Sources/backend/app/rag/blocks/query_processing/query_understanding/profile_understanding.py;
Sources/backend/app/rag/blocks/evidence/evidence_sufficiency/applicability_sufficiency.py (`_extract_branches`);
Sources/docs/agent_tasks/T39.result.md; existing AAES+ tests (grep -l aaes_llm Sources/backend/tests).

Allowed write paths: Sources/backend/app/rag/aaes_llm.py, the two block files above,
Sources/backend/tests/test_aaes_plus_v5.py (new), Sources/docs/aaes_spec.md (AAES+ section only),
Sources/docs/agent_tasks/T42.result.md.
Do not touch: aaes.py behaviour (you may import from it), presets, registry, any rules-mode or llm-mode behaviour,
labels, evaluators, Report/. Do not commit or push.

Spec — Step 1, mode "both" only (profile_understanding.py):
- Classify each rules value of the CURRENT question by how it was found:
  self   = a first-person self-statement: the quote is in a sentence with "I'm", "I am", "I'm a/an", "I study", "my"
           ownership before the value (e.g. "I'm a Seoul campus student", "I am at ERICA", "I'm an exchange student");
  hypothetical = the quote lies in a clause opened by "if I were", "if I was", "suppose", "imagine", "what if",
           "hypothetically", "let's say" (clause = from the cue to the end of the sentence);
  mention = anything else (e.g. a campus word alone, "What about ERICA students?").
  Put the classifier in aaes_llm.py as a pure function `rule_kind(text: str, quote: str) -> str` with doctests.
- A rules value of kind "hypothetical" or "mention" is kept only if the LLM extracted the same attribute with the
  same value (valid, quote-verified); otherwise that attribute becomes missing (then scope defaults apply as today).
  "self" values win as today (rules over LLM). Earlier-turn (remembered) values keep today's behaviour.
- Record in trace_details: "dropped_unconfirmed": [{"attribute", "value", "kind"}].

Spec — Step 3, step3_mode "both" only (_extract_branches):
- After the per-set extractions, if every set has an answer (no NONE / -1) and the lexical groups number >= 2:
  T39 rule first — if the answers' numbers differ (compare the numbers each answer contains), keep the split, no LLM.
  Otherwise make ONE LLM call (new prompt SAME in aaes_llm.py): the question plus one answer per group →
  {"same": true|false, "difference": "<at most 15 words>"}; parse/validate like the other parsers (invalid → keep the
  rules' split, count a fallback "same"). same=true → ANSWER with reason "same_meaning"; false → keep the split.
- NONE (a set without an answer) keeps today's behaviour: that group is referred, still a split, no SAME call.
- Record trace_details["same_check"] = {"groups", "same", "difference"} or the skip reason.

Tests that must pass: all existing backend tests (RRRR/A0 and llm modes unchanged) + new tests with a fake LLM:
the probe "If I were a master's student at ERICA, could I take the TOPIK class?" in both mode drops campus and
degree_level unless the fake LLM confirms them; "I'm a Seoul campus student." keeps campus=seoul; a bare
"What about ERICA students?" drops campus without LLM confirmation; SAME true merges two wordings; differing
numbers never call SAME; a NONE set never calls SAME; invalid SAME JSON keeps the split.
Verify with: cd Sources/backend && pytest -q
Human runs (Claude Code): dev measurement through the runner with Ollama.
Done when: AGENTS.md Definition of done items 1, 4, 5.
