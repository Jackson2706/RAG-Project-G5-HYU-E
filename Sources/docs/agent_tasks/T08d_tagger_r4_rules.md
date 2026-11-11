# T08d — Tagger rule fixes for r4: stated status, year ranges, visa target, rule 5b, LLM off
Owner: Codex · Reviewer: Claude Code · Phase: P4 (→ Gate G2b)

Goal: Fix the rule tagger for the failures the automated audit found on r3 (PLAYBOOK A20, A21).
Claude Code wrote the tests first: `Sources/backend/tests/test_tagger_r4.py` with 14 real r3 chunks in
`tests/fixtures/applicability_chunks_r4.json` (each case has a `note`). 14 tests fail now. Make all of
them pass without editing the tests or the fixture, and keep every existing test passing.

Read first:
- AGENTS.md, PLAYBOOK Amendments A6, A17, A20, A21;
- `Report/notes/tag_audit_rules.md` (rules 5b and 8);
- `metadata_extraction/applicability_extractor.py`;
- `app/rag/pipeline.py` (`_tag_chunks`);
- the test file and its fixture.

Allowed write paths:
- `applicability_extractor.py`;
- `Sources/scripts/ingest_snapshot.py` (dry-run output only);
- new tests in `Sources/backend/tests/test_tagger_r4_extra.py` if you need them;
- `Sources/docs/aaes_spec.md` (the tagging-rules section);
- `Sources/docs/agent_tasks/T08d.result.md`.

Do not touch: `app/rag/applicability.py`, existing tests and fixtures, `Report/`, `Sources/data/`, the index,
the LLM fallback code and its cache (they stay for later use; only the bucket for "LLM off" changes).

Spec:
1. **Admission guides (rule 8).** In a document whose title matches `ADMISSION_GUIDE`:
   - every chunk gets `academic_status=["applicant"]`, with or without the word "applicant" in the chunk
     (R01). Evidence: the first of "applicant(s)/application/admission" in the chunk if present; otherwise no
     evidence entry (method stays "rule");
   - a chunk that describes the acceptance procedure gets `["admitted_not_enrolled"]` instead: "Successful
     candidates", "certificate of admission" / "Admission Certificate", "After Deposit payment",
     "admission result" (R02, R03);
   - information about leave of absence inside the guide does not change it (R04 stays applicant).
2. **Stated status only (A21 decision c).** `enrolled` comes only from stated wording: "currently enrolled",
   "enrolled students", "students who (are) enrolled (at)", "currently in school". Never from an audience
   such as "international students", "freshmen" or a scholarship for current students (R09).
   - A leave-of-absence application notice (title has "Leave of Absence", not "Return") → `["enrolled"]`
     only; the topic "leave of absence" is not the audience (R05, R06).
   - A "Return to School" / re-registration notice → `["leave_of_absence"]` only (R07).
3. **Ineligibility lists.** Extend `NEGATED` so a parenthesised or colon list after "Ineligibility",
   "Ineligible", "not eligible" gives no values for `student_type`, `degree_level` and `academic_status`
   (R08). Add `degree_seeking` for "Degree Program Students" (R08).
4. **Year.** Collect every range in the chunk and take the union: "Year 1-2", "Year 3-4", "Year 3, 4",
   "Bachelor's degree 1~2 years / 3~4 years", "First year … Third and fourth years" (R10, R11). A duration
   ("four-year scholarship", "1 year", "up to 2 years") is never a year (R14). The C01 single-row case stays
   `["1","2"]`.
5. **Visa target.** In a change of status ("change … from <old> to <new>", "from D-4 visa to D-2 visa",
   "changed to a job seeker visa (D-10)"), keep only the new visa (R12 → D-10, R07 → D-2). Generalise the
   existing `transfer` branch; do not tag the old visa.
6. **Rule 5b.** When a TOPIK threshold is joined by "or" (or listed as alternatives in one sentence / one
   `Sort:` row) with an option outside the vocabulary — Social Integration Program, KIIP, IIE level, King
   Sejong Institute, a pre-assessment score — write no `topik_level` constraint and no `any_of` for it. Add the
   whole alternative (the sentence or row, trimmed to ≤ 200 chars) to `requirements` (R11, R12). A plain
   threshold stays a constraint. The TOPIK-or-English `any_of` rule (C13) is unchanged.
7. **LLM off → `rule_cue_unknown`.** Add `rule_cue_unknown` to `TAG_BUCKETS` (after `rule_unconditioned`).
   When the LLM fallback is disabled, a chunk with no rule constraint, no `any_of` and an `LLM_CUE` match goes
   to `rule_cue_unknown`; `pipeline._tag_chunks` already maps it to `condition_status="unknown"` — add a test
   that it does. `llm_called` stays 0 (R13).
8. **Dry run.** `ingest_snapshot.py --dry-run --no-llm` prints the partition estimate including
   `rule_cue_unknown`, and the counts of chunks with `applicant`, `admitted_not_enrolled`, `enrolled`, a
   year constraint, and a rule-5b requirement.

Tests that must pass:
- `cd Sources/backend && pytest -q` (including `tests/test_tagger_r4.py`, written first by Claude Code);
- `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`;
- `cd Sources && python -m evaluation.runner --suite all --dry-run`;
- `cd Sources && python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r4 --no-llm --dry-run`
  (paste the output into the result note).

Human runs: nothing (Claude Code gives the r4 build command after review).

Done when: AGENTS.md Definition of done is met, and `T08d.result.md` lists each spec item with its test and
the dry-run numbers.
