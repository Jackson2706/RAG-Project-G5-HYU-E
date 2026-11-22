# T10b — Tag audit: Wilson intervals, bucket-weighted recall, free-text columns, LLM-TOPIK floor
Owner: Codex · Reviewer: Claude Code · Phase: P4

Goal: Extend the T10 audit (`Sources/labeling/audit_tags.py`) per PLAYBOOK Amendment A10.

Read first: AGENTS.md, PLAYBOOK "Amendments" A6, A8, A10, `Sources/labeling/audit_tags.py`,
`Sources/labeling/tests/test_audit_tags.py`, `Sources/docs/agent_tasks/T10.result.md`.

Allowed write paths: `Sources/labeling/` (code and tests), `Sources/docs/aaes_spec.md`
(Tag audit section), `Sources/docs/agent_tasks/T10b.result.md`.

Do not touch: `Report/`, the index, the tagger.

Spec:
1. **New sampling floor.** Add ≥ 6 chunks whose `topik_level` came from the LLM
   (`extraction_method.topik_level == "llm"`). Keep all the T10 floors, and print the achieved
   count for this one too.
2. **Sidecar file.** `sample` also writes `<csv stem>.meta.json` next to the CSV, with:
   - `index_id`, `seed`, `n`;
   - the achieved stratum counts;
   - the index's full bucket partition, read from `manifest.applicability.partition` (the six A6
     buckets and their sizes over all chunks).

   `score` reads it. If it is missing, `score` fails with a clear message.
3. **Two free-text columns** at the end, before `reviewer`:
   - `out_of_vocabulary_condition`: a condition the vocabulary cannot express, e.g. "GPA ≥ 3.0" or
     "nationality".
   - `audience`: `applicant`, `admitted`, `enrolled`, or several joined with `|`. Validate this one
     against those values.

   Neither is scored. `score` lists them in `scores.md`: OOV conditions with their counts, and the
   audience distribution.
4. **Wilson 95% intervals** (z = 1.96) for every precision and recall: per attribute, and in every
   split.
   - Formula: center = (p + z²/2n)/(1 + z²/n); half = z·sqrt(p(1−p)/n + z²/4n²)/(1 + z²/n).
   - n = TP+FP for precision, and n = TP+FN for recall.
   - At n = 0 the interval is null.
   - Add a hand-computed example in the docstring and in a test, e.g. 8/10 → [0.490, 0.943].
5. **Bucket-weighted recall** per attribute, next to the raw recall.
   - For each bucket b, the weight is w_b = N_b / n_b: N_b chunks of bucket b in the index (from the
     sidecar), n_b reviewed chunks of bucket b in the sample.
   - recall_w = Σ w_b·TP_b / Σ w_b·(TP_b + FN_b).
   - A bucket with n_b = 0 but N_b > 0 is listed as "not sampled", and its weight is left out.
   - Interval: use Wilson with n = the raw TP+FN, and mark it with
     `# shortcut: Wilson on raw n for a weighted proportion; use a bootstrap if the gate is borderline`.
   - Precision stays raw. It is per predicted value, and the sample floors already cover the
     buckets that predict.
6. **G2 table** in `scores.md`. One row per gated attribute, with these columns:
   - occurrences;
   - precision with its CI;
   - recall (raw) with its CI;
   - recall (weighted) with its CI;
   - pass/fail, where pass = precision ≥ 0.8 AND weighted recall ≥ 0.7 (point estimates). Show the
     CI next to it.

   Below the table, add one line per method (rule / llm) with the same metrics.

Tests that must pass:
- the Wilson example above;
- weighted recall on a hand-made sheet with two buckets of different sizes, computed by hand in the
  docstring;
- a missing sidecar is a clear error;
- an `audience` value outside the list is a validation error;
- the TOPIK floor is met on the synthetic index (extend the conftest to have ≥ 6 such chunks);
- all T10 tests;
- `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`.

Human runs: nothing.

Done when: AGENTS.md Definition of done is met, and `T10b.result.md` is updated, including the
team's filling instructions for the two new columns.
