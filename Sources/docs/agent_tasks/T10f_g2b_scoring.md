# T10f — G2b scoring: coverage, resolved and strict recall, unknown share, side-by-side report
Owner: Codex · Reviewer: Claude Code · Phase: P4 (→ Gate G2b)

Goal: Add the G2b metrics of PLAYBOOK A23.3 to `labeling.auto_audit`, on top of T10d. Code and tests only.

Read first: AGENTS.md; PLAYBOOK A6, A14, A20, A21, A23; `Sources/labeling/auto_audit.py` (after T10d) and
`T10d.result.md`; `audit_tags.py` (`wilson_interval`, `bucket_weighted_recall`: reuse, do not copy).

Allowed write paths: `Sources/labeling/auto_audit.py`, new tests in `Sources/labeling/tests/`,
`Sources/docs/aaes_spec.md` (Tag audit section only), `Sources/docs/agent_tasks/T10f.result.md`.

Do not touch: the backend, `Report/`, `Sources/data/`, existing tests.

Spec:
1. **Quota.** `sample --quota BUCKET=N` (repeatable) overrides a scaled default. The G2b fresh sample uses
   `--n 100 --quota rule_cue_unknown=30`.
2. **Resolved vs unknown.** A chunk is *unknown* when its stored `condition_status` is `unknown`
   (bucket `rule_cue_unknown`, `llm_rejected`, `llm_errors`); otherwise *resolved*. Campus, scope and
   effective_term are always resolved (they never depend on the cue).
3. **Per attribute, in `compare` and `finalize`:**
   - `coverage` = reference occurrences (chunks with ≥ 1 reference value) in resolved chunks / all
     reference occurrences, with a Wilson interval;
   - `precision`, `recall`, `weighted_recall` on resolved chunks only (the gate numbers);
   - `strict_recall` and `strict_weighted_recall`: all chunks, every reference value on an unknown chunk
     counts as a miss;
   - all with Wilson 95% intervals; weights from the index partition in `sample_meta.json`.
4. **Unknown share.** Among sampled unknown chunks: the share whose reference has any constraint or
   `any_of` (Wilson interval), and that share × the index's unknown count (e.g. 387) as an estimated
   number of truly conditioned unknown chunks, with the interval scaled the same way. Also the top
   attributes in those chunks.
5. **Gate.** `g2.passed` uses resolved precision ≥ 0.8 and resolved weighted recall ≥ 0.7 for attributes
   with ≥ 5 occurrences (unchanged rule). Report coverage and strict recall next to it in the same row.
6. **`report --side-by-side OUT_A OUT_B --to FILE.md`**: one table per attribute row with the final
   scores of two audit folders next to each other (columns: occurrences, coverage, precision, recall,
   weighted recall, strict recall, gate) for A = old sample on r4 and B = fresh sample, plus the unknown
   share of each. The limitation line comes first.

Tests that must pass (offline, mongomock, synthetic r4-like index with `rule_cue_unknown` chunks):
- a hand-made 5-chunk case (2 unknown) with coverage, resolved recall and strict recall computed by hand in
  the docstring;
- the unknown-share estimate and its interval on a hand-made case;
- `--quota` overrides the scaled default;
- `report --side-by-side` on two small folders;
- all existing suites: `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`, and
  `cd Sources/backend && pytest -q`.

Human runs: nothing.

Done when: AGENTS.md Definition of done is met, and `T10f.result.md` has the full command sequence for G2b
(reuse old sample with `reference_r8b.jsonl` → compare → review → finalize; fresh sample → blind reference →
compare → review → finalize; side-by-side report).
