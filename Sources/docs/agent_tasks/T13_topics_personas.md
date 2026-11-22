# T13 — Topics (titles and headings only) and personas
Owner: Codex · Reviewer: Claude Code · Phase: P5 (after G3)

Goal: Write the two inputs for question drafting (T14): a topic list built from snapshot titles and
headings only, and 10–12 personas with full gold profiles in vocabulary v1. Question writers must never see
page bodies, so the topic file contains no body text.

Read first: AGENTS.md (Labeling rules), PLAYBOOK Appendix D and A19, A22;
`Sources/data/HYU/labels/GUIDELINES.md` v1.0 (sections 2, 7, 8); `Sources/backend/app/rag/applicability.py`;
`Sources/labeling/_snapshot.py` and `validate.py` (`_validate_profile`).

Allowed write paths: new `Sources/labeling/topics.py`, new `Sources/labeling/personas.py` (checker only),
new tests in `Sources/labeling/tests/`, `Sources/data/HYU/labels/topics.jsonl`,
`Sources/data/HYU/labels/personas.json`, `Sources/docs/agent_tasks/T13.result.md`.

Do not touch: the snapshot files, the backend, `Report/`, other label files, the index.

Spec:
1. **`python -m labeling.topics --snapshot hyu-20261110-97dc1269`** (from `Sources/`; reads the local snapshot,
   no network) writes `labels/topics.jsonl`, one row per document:
   `doc_id`, `site`, `title`, `headings` (English heading spans only, in order, deduplicated, each ≤ 120 chars),
   `post_date`, `superseded_by`, `file_type` (html/pdf/hwp/… from the source URI or attachment name),
   `korean_only` (true when the document has no English body span). **No body text, no URLs with query
   strings.** Mask e-mail addresses in titles and headings. Read the snapshot through `_snapshot.py`; do NOT
   print or log body text.
2. **`labels/personas.json`**: 10–12 personas, each `{persona_id, name (a role, not a person's name, e.g.
   "ERICA D-4 language student"), description (one line), gold_profile}`. `gold_profile` has a value for
   EVERY v1 attribute (one value each; `year` only for undergraduates, otherwise omitted), using v1 values.
   - Minimums (GUIDELINES section 7): ≥ 2 English-track students with low or no TOPIK; ≥ 2 ERICA students
     who will ask visa questions (D-2, D-4, D-10 between them); ≥ 1 applicant; ≥ 1 admitted student with
     `korean_standard: fail`; ≥ 1 completed coursework; ≥ 1 graduate student; both campuses; every
     `degree_level` and `student_type` value at least once across personas.
   - `academic_status: applicant` only for the applicant persona(s) (scope default, A17).
   - Personas whose profile will change in a multi-session case get `updates`: a list of
     `{attribute, from, to, why}` (≥ 3 personas: D-4 → D-2, enrolled → completed_coursework,
     korean_standard fail → pass).
3. **`python -m labeling.personas`** checks `personas.json`: v1 values (import the vocabulary; never copy
   it), every minimum above, `updates` values valid; prints a coverage table (attribute × value → persona
   ids); exits 1 on a failure.

Tests that must pass:
- topics: on a synthetic 3-document snapshot (per A1), the output has no body text (assert none of the body
  strings appears in the file), masks an e-mail in a heading, marks a Korean-only document;
- personas: the checker rejects a value outside v1, a missing attribute, and a set that lacks an English-track
  persona; the real `personas.json` passes;
- `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`, `cd Sources/backend && pytest -q`.

Verify with: `cd Sources && python -m labeling.topics --snapshot hyu-20261110-97dc1269 && python -m labeling.personas`
(local files only; allowed). Report the topic count, the Korean-only count, and the coverage table.

Human runs: nothing.

Done when: AGENTS.md Definition of done is met; `T13.result.md` has the counts and the coverage table.
