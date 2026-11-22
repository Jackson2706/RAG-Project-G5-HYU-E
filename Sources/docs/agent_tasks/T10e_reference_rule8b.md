# T10e — Re-check the r3 audit reference under audit rule 8b (annotation pass, blind)
Owner: Codex (annotator) · Reviewer: Claude Code · Phase: P4 (→ Gate G2b)

Goal: The r3 reference (`reference_normalized.jsonl`) was written before audit rule 8b. Re-check ONLY its
`academic_status` values (in `constraints` and `any_of`) and the matching `evidence` entries under the
current rules, so the old sample can be scored fairly on r4 (PLAYBOOK A21).

Read: `Report/notes/tag_audit_rules.md` (all of it; rules 8 and 8b decide this pass), and, in
`Report/results/tag_audit/hyu_20261110_97dc1269_r3/auto/`, only `blind_inputs.jsonl` and
`reference_normalized.jsonl`.

Do NOT open any other file in that folder (no `disagreements*`, `decisions*`, `scores*`, `sample_meta*`,
`causes*`), any `Report/results/index_reports/` file, or any system output. You never see predicted tags.

Write (only these):
- `Report/results/tag_audit/hyu_20261110_97dc1269_r3/auto/reference_r8b.jsonl`: the same 150 rows in the same
  order, identical except `constraints.academic_status`, `academic_status` inside `any_of` sets (drop a set
  that becomes empty; if one set is left, apply the one-set rule 5b note: move it to `constraints`),
  `evidence.academic_status` (an exact substring of the chunk text), `audience`, and `notes` (append
  `8b: <old> -> <new>` when you change a row).
- `Report/results/tag_audit/hyu_20261110_97dc1269_r3/auto/reference_r8b_NOTE.md`: how many rows changed, per
  old→new value, and 3 examples quoting the text.

Rules for this pass: apply 8 and 8b exactly. An audience ("international students", "freshmen", a scholarship
for current students) gives no `academic_status`. A stated status, an exclusion list that removes every other
status, a leave-of-absence application (→ enrolled) or a return-to-school notice (→ leave_of_absence) does.
Every chunk of an admission guide (title: admission guide/guideline, GKS application forms & guidelines,
recruitment of students) is `applicant`, except acceptance sections (→ `admitted_not_enrolled`).

Check before finishing: 150 rows, same chunk_id order, every value in vocabulary v1, every evidence quote a
substring of its chunk text (whitespace-normalized), no field other than the allowed ones changed. Write a
small throwaway check script in `/tmp` if you need one; do not add it to the repo.

Human runs: nothing.
