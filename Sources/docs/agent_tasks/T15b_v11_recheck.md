# T15b — Codex: re-check batches 01-03 under GUIDELINES v1.1, then annotate 04-06
Owner: Codex · Reviewer: Claude Code, then humans adjudicate · Phase: P5 (PLAYBOOK A30)

Everything in `T15_codex_annotation.md` still holds (read it first: read-only list, do-not-open list,
row format, validation), with these changes:
- The rulebook is `Sources/data/HYU/labels/GUIDELINES.md` **v1.1**; section 9 wins over sections 1-8.
- Every row you write has `case_version: "1.1"`.
- Each exec does exactly ONE step, named in the prompt.

**Step `recheck NN` (NN = 01, 02, 03).** Re-read every row of `annot_codex/batch_NN.jsonl` against v1.1 and its
snapshot spans. Change ONLY these fields where v1.1 requires it: `answerability`, `expected_behavior`,
`acceptable_behaviors`, `branch_attributes`, `gold_evidence`, `inapplicable_evidence`, `outdated_evidence`,
plus `gold_profile` / `stated_profile` under 9.5 and `reference_answer` / `required_facts` only when the
behaviour changed. Rewrite the batch file in place (all 30 rows, `case_version` "1.1"). Append one line per
changed field to `annot_codex/v11_changes.jsonl`:
`{"case_id", "field", "old", "new", "reason"}` (reason cites the v1.1 rule, e.g. "9.1: 1 of 2 facts supported").
Unchanged rows get no change line.

**Step `annotate NN` (NN = 04, 05, 06).** As T15, for `annotation_input/batch_NN.jsonl`, under v1.1.

After each step: `cd Sources && python -m labeling.validate data/HYU/labels/annot_codex/batch_NN.jsonl --annotation`
exits 0, and NOTES.md records the step as done (plus any v1.1 questions).
