# T08c — Tagger for vocabulary v1: korean_standard, applicant, any_of, preferences, postcheck p1, prompt v3
Owner: Codex · Reviewer: Claude Code · Phase: P4

Goal: Update the rule tagger and the LLM postcheck to vocabulary v1 (PLAYBOOK Amendments A13 and
A17). Claude Code already changed `app/rag/applicability.py` (v1 values, `any_of`,
`condition_fit`, `SCOPE_DEFAULTS`) and wrote the tests first in
`Sources/backend/tests/test_applicability.py`. 11 of them fail now; make every one pass without
editing the tests or `tests/fixtures/applicability_chunks.json`.

Read first:
- AGENTS.md, PLAYBOOK Amendments A9, A13, A17;
- `Sources/backend/app/rag/applicability.py`;
- `Sources/backend/tests/test_applicability.py`, from "vocabulary v1" on, and the `note` of fixture
  cases C07, C08, C13;
- `metadata_extraction/applicability_extractor.py`;
- `app/rag/pipeline.py` (`_tag_chunks`);
- `Sources/scripts/ingest_snapshot.py`;
- `Sources/labeling/audit_tags.py` (frequency only).

Allowed write paths:
- `applicability_extractor.py`;
- `pipeline.py` (`_tag_chunks` summary only);
- `scripts/ingest_snapshot.py` (manifest fields and dry-run output only);
- `Sources/labeling/audit_tags.py` (`frequency`: count `any_of` and `korean_standard`);
- new tests in `Sources/backend/tests/test_vocabulary_v1_extra.py` if you need them;
- `Sources/docs/aaes_spec.md` (the tagging-rules section);
- `Sources/docs/agent_tasks/T08c.result.md`.

Do not touch:
- `app/rag/applicability.py`;
- the existing tests and the fixture;
- `Report/`, `Sources/data/`;
- the index.

Spec:
1. **`korean_standard`** (rules). "Satisfied (or being exempted) the Korean Language Standards" →
   `["pass", "exempt"]`. "Exempted" alone → `["exempt"]`. "did not satisfy the Korean Language
   Standards" or "Korean Standard Fail" → `["fail"]`. The phrase is no longer a requirement (C07,
   C08).
2. **`applicant`.** Add `academic_status=applicant` ONLY when the document is an admission guide.
   - That means its title matches an admission-guide pattern: "Admission Guideline", "Admission
     Guide", "Application Guideline(s)", "Application Forms & Guidelines", "Recruitment of …
     students".
   - It does NOT include acceptance guides, which stay `admitted_not_enrolled`, and NOT
     scholarships whose text says "applicants".
   - Inside an admission guide, the chunk must mention applicants, application or admission.
3. **Alternative sets (`any_of`)**, only when the text joins two groups with "or".
   - The case to handle: a TOPIK condition, then "or", then IELTS/TOEFL/TEPS/English track, within
     one sentence or one list line.
   - Write `any_of = [{topik_level: <levels>}, {english_track: ["yes"]}]`:
     - the levels come from a threshold if there is one;
     - "valid TOPIK certificate" with no level means 1–6.
   - Remove those attributes from `constraints` (C13).
   - Record `extraction_method["any_of"] = "rule"` and evidence for `any_of`.
4. **Preference wording is never a constraint**, for rules and LLM alike. If the matched phrase,
   or the LLM's evidence quote ±80 characters, contains "prefer", "additional point(s)", "bonus",
   "advantage" or "optional", drop that attribute. When the phrase came from the chunk, add it to
   `requirements` with a `preference:` prefix.
5. **Postcheck p1** (`POSTCHECK_VERSION = "p1"`, LLM answers only), applied in this order:
   - **Fixed mappings.** These are recorded in `trace_details["llm_fallback"]["mapped_fields"]`
     ({field: "from → to" or "dropped"}) and are NOT rejections:
     - `visa` values starting with `F` or `D-` that are not in the vocabulary → `other`;
     - `student_type` `international` or `volunteer` → dropped;
     - the attribute `semester` → dropped.
   - **Normalized substring match.** Collapse whitespace and ignore case when looking for the
     evidence quote. If it is found, store the EXACT chunk substring as the evidence.
   - **Every-value drop** (already present).
   - **Labeled rejection units.** Each rejected field is one unit, with a reason label from a fixed
     set: `unknown_attribute`, `value_outside_vocabulary`, `missing_quote`, `quote_not_in_text`,
     `every_value`, `preference`, `bad_json`.
     - The summary reports `llm_rejected_fields_by_reason` (units) and `llm_rejected` (chunks)
       separately.
     - Map the old free-text reasons to these labels.
6. **Prompt v3** (`TAG_PROMPT_VERSION = "v3"`). It lists the v1 vocabulary (`korean_standard`,
   `applicant`; no `short_term`) and adds one line: "Do not tag preferences ('preferred',
   'additional points', 'optional')". The LLM is not asked for `any_of`; only the rules produce it.
   The cache key already includes the prompt version, so v2 entries stay in the cache file for r2.
7. **Manifest and dry run.**
   - `applicability.llm` records `postcheck_version` and `vocabulary_version`.
   - The ingest dry run prints the partition estimate it already prints, plus the chunks with
     `any_of`, with `korean_standard` and with `applicant`.
   - `audit_tags frequency` counts `any_of` sets and the new attribute.

Tests that must pass:
- `cd Sources/backend && pytest -q`: all tests, including the 50 in `test_applicability.py`;
- `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`;
- `python -m evaluation.runner --suite all --dry-run`;
- `python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r3 --dry-run`.

Paste the dry-run output into the result note.

Human runs: nothing (Claude Code gives the r3 build command after review).

Done when: AGENTS.md Definition of done is met, and `T08c.result.md` lists each rule with its test
and the dry-run numbers.
