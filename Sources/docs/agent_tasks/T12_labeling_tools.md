# T12 — Labeling tools: search, validate, agreement, freeze
Owner: Codex · Reviewer: Claude Code · Phase: P5 (allowed before G2 by Amendment A11; no labels yet)

Goal: Write the tools the labeling phase needs. Labels follow PLAYBOOK Appendix D and the draft
guideline `Report/data/HYU/labels/GUIDELINES.md`. Claude Code wrote the split/freeze tests first:
`Sources/labeling/tests/test_freeze.py`. Make them pass without changing them.

Read first:
- AGENTS.md, and PLAYBOOK Appendix D plus Amendments A4, A7, A11;
- `Report/data/HYU/labels/GUIDELINES.md` (sections 2 and 7);
- `Sources/labeling/tests/test_freeze.py`;
- `Sources/backend/app/rag/snapshot.py` (`load_snapshot`, offsets);
- the row structure of `Report/data/HYU/snapshots/hyu-20261110-97dc1269/documents.jsonl`:
  `doc_id`, `source_uri`, `title`, `campus`, `text`, `spans[{kind, char_start, char_end}]`,
  `post_date`, `superseded_by`.

Allowed write paths:
- `Sources/labeling/` (new modules and tests; leave `audit_tags.py` alone);
- `Sources/docs/agent_tasks/T12.result.md`.

Do not touch:
- `Report/` (no label files are created in this task);
- `test_freeze.py`;
- the backend.

Spec. Each tool is a module with a small CLI (`python -m labeling.<tool>`, run from `Sources/`).
1. **`search.py`:** BM25 over the snapshot's spans, so annotators can find evidence offsets.
   - `python -m labeling.search "part-time work hours" [--snapshot ID] [--k 10] [--campus erica]`
     prints rank, `doc_id`, `campus`, `char_start`–`char_end`, the span kind and 200 characters of
     text.
   - The unit is one snapshot span, plus a heading-to-next-heading window per section, so whole
     sections can be cited.
   - Use `rank_bm25` if it is in `Sources/backend/requirements.txt` or the env. Otherwise write a
     30-line BM25 with k1 = 1.5 and b = 0.75 and give it a test with a hand-computed score. No new
     dependency.
   - Offsets are into the snapshot row `text`, exactly the `char_start`/`char_end` that labels store.
2. **`validate.py`:** `python -m labeling.validate FILE.jsonl [--snapshot ID]`.
   - **Schema:** the Appendix D fields and types.
     - `answerability` ∈ {answerable, partial, unanswerable, external_only, korean_only,
       unanswerable_unreadable};
     - `expected_behavior` ∈ {answer, conditional_answer, clarify, abstain};
     - `acceptable_behaviors` ⊇ {`expected_behavior`};
     - `slice` ∈ the five slices; `split` ∈ {dev, test}, or absent before the freeze;
     - `origin` and `annotator` follow the AGENTS.md formats.
   - **Vocabulary:** `stated_profile`, `gold_profile` and `branch_attributes` use only
     vocabulary attributes and values. Import `VOCABULARY` from
     `Sources/backend/app/rag/applicability.py`; never copy it. `stated_profile` must agree with
     `gold_profile` wherever both have a value, except in `multi_session` cases with a stated
     update.
   - **Evidence spans:** every one has an existing `doc_id`, with
     `0 ≤ char_start < char_end ≤ len(text)`. It is also checked against the snapshot.
     - `gold_evidence` entries need `applies_to_gold_profile: true`;
     - `inapplicable_evidence` entries need a non-empty `why`;
     - an `outdated_evidence` doc must not be the newest version of its family when the snapshot
       links one;
     - `answer` / `conditional_answer` cases need at least one `gold_evidence` span;
     - `abstain` cases with `answerability: answerable` are an error.
   - **Rules:** `conditional_answer` and `clarify` need a non-empty `branch_attributes`.
     `case_id` values are unique.
   - Output: one line per violation (`case_id: field: message`). Exit 1 if there is any.
3. **`agreement.py`:** `python -m labeling.agreement A.jsonl B.jsonl --out DIR`, on the cases both
   files have (by `case_id`).
   - Cohen's κ for `answerability` and for `expected_behavior`, with a hand-computed test example.
   - Jaccard of `branch_attributes`, as the mean over cases. Both empty counts as 1.0.
   - Span-overlap F1 of `gold_evidence`, at the character level per case, then the mean.
   - `adjudication.csv`, one row per case: `case_id`, the two annotators' values for each compared
     field, `agree` (yes/no), and empty `final_*` and `adjudicator` columns.
   - `agreement.md`, with the numbers and the count of disagreements per field.
4. **`freeze.py`:** exactly the contract in `test_freeze.py`'s docstring.
   - Strata are (`slice`, `gold_profile.campus`).
   - Proportional allocation with the largest-remainder rule, then a seeded shuffle inside each
     stratum. Sort the cases by `case_id` before shuffling, so the input order does not matter.
   - `freeze` sets `split` on every case it writes.
   - `FROZEN.sha256` uses the `sha256sum` format (`<hex>  <file>`).
   - CLI: `python -m labeling.freeze LABELS.jsonl --out Report/data/HYU/labels --dev-size 50`.
     The default seed is 13.
   - Also write `verify_frozen(out_dir)` for the runner later. That is the same as `verify`.

Tests that must pass:
- `test_freeze.py` (by Claude Code; do not edit it);
- new tests:
  - `search` on a 3-document synthetic snapshot built in the real row structure (A1): the right
    span ranks first, and its offsets cut out the exact text;
  - `validate`: one valid case, and one case per rule above that fails with the expected message;
  - `agreement`: κ on a hand-computed 2×2 example in the docstring, Jaccard, span F1, and the
    adjudication CSV columns;
  - one real-data smoke test: `search` on the committed snapshot returns results for "alien
    registration". Skip it if the snapshot is absent;
- all existing suites: `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`.

Verify with: the command above.

Human runs: nothing.

Done when: AGENTS.md Definition of done is met, and `T12.result.md` lists every CLI with one example
command each.
