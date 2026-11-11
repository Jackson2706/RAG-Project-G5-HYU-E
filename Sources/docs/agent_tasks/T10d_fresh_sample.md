# T10d — Audit tools for r4: new bucket, fresh sample, re-used sample, output folder
Owner: Codex · Reviewer: Claude Code · Phase: P4 (→ Gate G2b)

Goal: Let `labeling.auto_audit` score r4 on (a) a FRESH stratified sample with none of the r3 sample's
chunks and (b) the old r3 sample re-used on r4, side by side (PLAYBOOK A20). Code and tests only.

Read first: AGENTS.md, PLAYBOOK A6, A14, A20, A21; `Sources/labeling/auto_audit.py`, `audit_tags.py`;
`Sources/docs/agent_tasks/T08d_tagger_r4_rules.md` (item 7: bucket `rule_cue_unknown`).

Allowed write paths: `Sources/labeling/auto_audit.py`, `Sources/labeling/audit_tags.py` (`BUCKETS` only),
new tests in `Sources/labeling/tests/`, `Sources/docs/aaes_spec.md` (Tag audit section),
`Sources/docs/agent_tasks/T10d.result.md`.

Do not touch: the backend, `Report/`, `Sources/data/`, existing tests.

Spec:
1. `BUCKETS` gains `rule_cue_unknown` (same order as `TAG_BUCKETS`). Bucket-family rule: `rule_cue_unknown`
   counts as the **rule** family for FN attribution.
2. Every command takes `--out NAME` (default `auto`): `OUT = RESULTS_DIR/tag_audit/<index_id>/<NAME>/`.
3. `sample --exclude META` (repeatable): drop every chunk_id listed in that `sample_meta.json` before
   sampling. Record the excluded files and their counts in the new `sample_meta.json`.
4. `sample --reuse META`: take exactly the chunk_ids of META (no quotas, no floors; fail if any is missing in
   the index), write `sample_meta.json` with the current index's buckets and partition, and do NOT write a
   new `blind_inputs.jsonl` — copy it unchanged from META's folder and check that its chunk texts equal the
   index texts (fail otherwise). The old reference can then be compared against r4.
5. Quotas scale with `--n` (round, base 150) and use only non-empty buckets. Default quotas:
   rule_tagged 50, rule_unconditioned 25, rule_cue_unknown 35, llm_tagged 20, llm_unconditioned 35,
   llm_rejected all, llm_errors all. A bucket with 0 chunks gets 0. Fill up to n from rule_tagged,
   rule_cue_unknown and llm_unconditioned (those present).
6. Floors scale the same way and are capped by what the (post-exclusion) index has: `min(floor, available)`.
   Report both the requested and the achieved floor; still fail if achieved < capped floor.
7. `compare --reference R --carry-decisions DIR` (optional): when a disagreement row (chunk, attribute,
   both value sets) is identical to a row decided in `DIR/decisions.jsonl` + `DIR/disagreements_key.json`,
   carry that decision over and write only the NEW rows to `disagreements.jsonl` for the reviewer. `finalize`
   merges carried and new decisions; the md report shows how many were carried.

Tests that must pass (offline, mongomock, synthetic index per A1, including a `rule_cue_unknown` bucket and
no LLM buckets):
- `--exclude` never returns an excluded chunk; quotas and floors scale for n=100; floors cap at availability;
- `--reuse` keeps the chunk_ids, recomputes buckets, copies blind inputs, fails on a changed text;
- `--carry-decisions` carries an identical row, does not carry a row whose values changed;
- `--out` writes to the named folder;
- all existing suites: `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`, and
  `cd Sources/backend && pytest -q`.

Human runs: nothing.

Done when: AGENTS.md Definition of done is met, and `T10d.result.md` has the exact command sequence for
r4: reuse old sample → compare (carry r3 decisions) → fresh sample (n=100, exclude r3 meta) → compare →
finalize.
