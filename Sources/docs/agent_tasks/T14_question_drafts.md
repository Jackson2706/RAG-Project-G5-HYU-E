# T14 — Draft questions from topics × personas (no page bodies)
Owner: Codex · Reviewer: Claude Code, then humans · Phase: P5 (after G3, PLAYBOOK A22/A25)

Goal: Draft candidate questions for the 180-case label set. Humans then delete unrealistic drafts and add their
own (≥ 30% of the final questions are human-written or human-edited). Draft MORE than the targets (about 230), so
humans can delete freely. This task writes questions only: no answers, evidence, behaviours or labels.

Read ONLY: AGENTS.md (Labeling rules); `Sources/data/HYU/labels/GUIDELINES.md` v1.0 (sections 1, 2, 3, 6, 7, 8);
`Sources/data/HYU/labels/topics.jsonl`; `Sources/data/HYU/labels/personas.json`.
Do NOT open: the snapshot (`Sources/data/HYU/snapshots/`), `raw/`, any index, `Report/results/`, any system output,
or any other label file. Never read page bodies; titles and headings in `topics.jsonl` are all you know.

Allowed write paths: new `Sources/labeling/drafts.py` (checker only), new tests in `Sources/labeling/tests/`,
`Sources/data/HYU/labels/drafts/questions_codex.jsonl`, `Sources/docs/agent_tasks/T14.result.md`.

Spec:
1. **One JSON object per line:**
   `{draft_id, slice, campus, persona_id, topic_doc_ids, question, session_history, intended_attributes,
   intended_answerability, why, annotator: "codex:<model>", origin: "agent_draft"}`.
   - `slice`: unconditional | conditional | temporal | negative | multi_session (GUIDELINES section 7).
   - `campus`: seoul | erica (the persona's campus; ERICA ≈ 40%).
   - `topic_doc_ids`: 1–3 `doc_id`s from `topics.jsonl` the question is about.
   - `session_history`: `[]`, except multi_session: 1–3 earlier user turns that state profile facts. At least 6
     multi_session drafts use a persona's `updates` (the later turn states the new value, e.g. D-4 → D-2).
   - `intended_attributes`: the v1 attributes the drafter expects to matter (a hint for annotators, not a label).
   - `intended_answerability`: the drafter's guess (answerable | partial | unanswerable | external_only |
     korean_only | unanswerable_unreadable). Use `unanswerable_unreadable` only for topics whose `file_type` is
     hwp or a scanned PDF hint; `korean_only` only for `korean_only: true` topics. At least 6 of each kind of
     negative draft (unanswerable, external_only, korean_only, unanswerable_unreadable) where topics allow.
   - `why`: one line on why a real student would ask it.
2. **Realism.** Write as a new international student types: short, sometimes informal, English. The question
   states only what that student would say; conditional drafts leave some attributes unstated on purpose
   (mix stated / unstated / partly stated). Questions about applying for admission come from the applicant
   persona and state it by their wording (section 8.2). Never copy a title verbatim as the question.
3. **Quotas** (drafts, about 1.25× the section 7 targets per slice × campus, rounded up): unconditional 48/32,
   conditional 32/25, temporal 17/7, negative 28/18, multi_session 13/10 (Seoul/ERICA). Every persona appears;
   no persona has more than 15% of the drafts.
4. **`python -m labeling.drafts check`** (from `Sources/`): validates the schema, v1 attribute names, persona ids,
   doc_ids that exist in `topics.jsonl`, unique `draft_id`s; prints counts per slice × campus vs the quota,
   per persona, and per intended answerability; exits 1 on a schema error.

Tests that must pass: the checker on a tiny synthetic drafts file (rejects an unknown persona, an unknown doc_id
and a duplicate id); `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`;
`cd Sources/backend && pytest -q`.

Verify with: `cd Sources && python -m labeling.drafts check` (local files only).

Human runs: review the drafts (delete, edit, add); then Claude Code commits and pushes.

Done when: AGENTS.md Definition of done is met; `T14.result.md` has the checker output.
