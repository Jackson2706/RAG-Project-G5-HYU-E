# T15 — Codex annotates all 180 cases (6 batches of 30)
Owner: Codex (primary annotator) · Reviewer: Claude Code, then humans adjudicate · Phase: P5 (PLAYBOOK A19, A26–A28)

Goal: Annotate every case in `Sources/data/HYU/labels/annotation_input/batch_01.jsonl` … `batch_06.jsonl` with the
full label schema, one output file per batch. Work batch by batch, in order. **Finish and validate each batch
before starting the next**, so a stop midway leaves complete batches.

Read ONLY:
- AGENTS.md (Labeling rules);
- `Sources/data/HYU/labels/GUIDELINES.md` v1.0, all of it (it is the rulebook);
- PLAYBOOK Appendix D (`Report/project/PLAYBOOK.md`, the label schema);
- the batch input files above;
- the snapshot `Sources/data/HYU/snapshots/hyu-20261110-97dc1269/documents.jsonl`, through
  `python -m labeling.search "<query>" [--campus seoul|erica] [--k 10]` (run from `Sources/`) and by reading
  the spans it returns.

Do NOT open: `labels/drafts/` (hints, quota view, review sheet), `labels/questions.jsonl`, `labels/personas.json`,
any other label or annotation folder (`annot_claude/` in particular), `Report/results/`, any index, the backend
code, or any system output. Never run the RAG system.

Write ONLY: `Sources/data/HYU/labels/annot_codex/batch_NN.jsonl` (NN = the input batch) and
`Sources/data/HYU/labels/annot_codex/NOTES.md` (per batch: done / not done, hard cases, guideline questions).

Each output row:
- copies `case_id`, `session_history`, `question` and `gold_profile` from the input unchanged;
- adds `case_version: "1.0"`, `snapshot_id: "hyu-20261110-97dc1269"`, `annotator: "codex:<your model>"`;
- adds every judgement field of Appendix D / GUIDELINES section 2: `stated_profile`, `branch_attributes`,
  `condition_sets` (only when the text says "or"), `answerability`, `expected_behavior`, `acceptable_behaviors`,
  `required_facts`, `gold_evidence`, `inapplicable_evidence`, `outdated_evidence`, `condition_scope`,
  `reference_answer`, `notes`;
- has NO `slice`, `origin` or `split` (the merge adds them).

Rules: GUIDELINES.md decides every judgement (stated vs gold profile, the applicant scope default and section 8.2,
the clarify threshold, missing campus as a branch, temporal and negative cases, national vs campus). Evidence
spans are exact `doc_id` + `char_start`/`char_end` into the snapshot `documents.jsonl` text. If the answer does
not exist in English in the snapshot, label it with the matching negative `answerability`, not a guess.

Check each batch before moving on:
`cd Sources && python -m labeling.validate data/HYU/labels/annot_codex/batch_NN.jsonl --annotation` must print
nothing and exit 0. Record the batch as done in NOTES.md only after it passes.

If you hit a usage limit: stop after the current batch passes validation (or leave the unfinished batch file out),
and make NOTES.md say exactly which batches are done.

Human runs: nothing. Claude Code commits and pushes after each session (A19).
