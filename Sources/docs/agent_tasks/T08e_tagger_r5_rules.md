# T08e — Last tagger round for r5: guide degree level, prior qualifications, student_type phrases, visa noise
Owner: Codex · Reviewer: Claude Code · Phase: P4 (→ Gate G2b, last round, PLAYBOOK A24)

Goal: Fix the r4 failures of the dev-100 audit sample. Claude Code wrote the tests first:
`Sources/backend/tests/test_tagger_r5.py` with 12 real r4 chunks in `tests/fixtures/applicability_chunks_r5.json`
(each case has a `note`). 14 tests fail now. Make all of them pass without editing the tests or the fixture, and
keep every existing test passing (including `test_applicability.py`, `test_tagger_r4.py`).

Read first: AGENTS.md; PLAYBOOK A21, A24; `metadata_extraction/applicability_extractor.py`; the test file and fixture.

Allowed write paths: `applicability_extractor.py`; `Sources/scripts/ingest_snapshot.py` (dry-run output only);
new tests in `Sources/backend/tests/test_tagger_r5_extra.py`; `Sources/docs/aaes_spec.md` (Rule-first
extraction section only); `Sources/docs/agent_tasks/T08e.result.md`.

Do not touch: `app/rag/applicability.py`, existing tests and fixtures, `Report/`, `Sources/data/`, the index,
the LLM fallback code.

Spec:
1. **Guide degree level.** Only when the chunk's own `title` or `heading_path` names an admission guide:
   - "Graduate Admission Guide(line)", "GKS-G …" (any year) → `degree_level = ["master", "doctoral"]`;
   - "Undergraduate Admission Guide(line)", "GKS-U …" → `["undergraduate"]`.
   - This value REPLACES any degree level found in the chunk text (a bachelor's certificate inside a graduate
     guide is a prior qualification: S02, S03). Method `rule`; evidence = the matching title / heading text
     (it is not in the chunk text, so store no evidence entry when it is not a substring of `text`).
   - Nothing outside such a guide inherits (the "outside" test).
   - Count the chunks that inherit in `ApplicabilityExtractor.summary["degree_inherited"]`, and print it in the
     dry run.
2. **Prior qualifications.** Everywhere: "must hold / have completed / holders of / graduated with a
   bachelor's (degree)", "completed your undergraduate program", "bachelor's degree (… ) or higher" as an
   entry requirement give no `undergraduate` (S06).
3. **Institution names.** "<Name> Graduate School of <field>" (a proper-noun name, e.g. in a partner list) gives
   no degree level (S07). The existing `GRADUATE` pattern still matches "graduate school students",
   "Graduate:" table cells, etc.
4. **student_type phrases.** `degree_seeking`: "enrolled in a degree program", "Degree programs", "masters/doctoral
   degree students". `language_program`: "language training … students", "language school program",
   "Language School" (S08–S10, S12). Keep the existing patterns.
5. **Visa noise.** No visa from a contact line ("Regarding … visa …, please contact", "inquiries") or a misuse
   warning ("abusing visa", "asylum", "countries subject to intensive management") (S04, S05, S11). Other visa
   mentions in the same chunk still count.
6. **Dry run.** `ingest_snapshot.py --dry-run --no-llm` also prints `degree_inherited` and the counts for
   degree_level, student_type and visa values.

Tests that must pass: `cd Sources/backend && pytest -q`; `cd Sources && pytest -q labeling/tests evaluation/tests
crawler/tests`; `cd Sources && python -m evaluation.runner --suite all --dry-run`;
`cd Sources && python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r5 --no-llm --dry-run`
(paste the output into the result note).

Human runs: nothing (Claude Code gives the r5 build command after review).

Done when: AGENTS.md Definition of done is met; `T08e.result.md` maps each spec item to its test and gives the
dry-run numbers.
