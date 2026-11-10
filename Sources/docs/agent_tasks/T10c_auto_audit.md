# T10c — Automated tag audit: sampling, blind inputs, comparison, disagreement review, scores
Owner: Codex · Reviewer: Claude Code · Phase: P4 (→ Gate G2)

Goal: Write the tools for the automated audit of PLAYBOOK A14 on the published index
`hyu_20261110_97dc1269_r3`. This task writes and tests code only. It does not annotate anything.
The two annotation passes are separate Codex runs, started by Claude Code later.

Read first:
- AGENTS.md, and PLAYBOOK Amendments A6, A10, A14, A17;
- `Report/notes/tag_audit_rules.md`;
- `Sources/labeling/audit_tags.py`: reuse `wilson_interval`, `bucket_weighted_recall`, the
  split logic and the bucket names. Do not copy them;
- `Sources/backend/app/rag/applicability.py` (v1 vocabulary, `any_of`).

Allowed write paths: new `Sources/labeling/auto_audit.py`, new tests in `Sources/labeling/tests/`,
`Sources/docs/aaes_spec.md` (Tag audit section), `Sources/docs/agent_tasks/T10c.result.md`.

Do not touch: `audit_tags.py` (import from it), the backend, `Report/`, `Sources/data/`.

Output folder: `OUT = Report/results/tag_audit/<index_id>/auto/`.

CLI (`python -m labeling.auto_audit <command>`, run from `Sources/`):
1. **`sample --index-id ID --n 150 --seed 20261111`.** Reads MongoDB. Claude Code runs it.
   - **Stratify by bucket × campus.**
     - Bucket quotas: rule_tagged 50, rule_unconditioned 25, llm_tagged 20 (or all, if fewer),
       llm_unconditioned 35, llm_rejected all (12), llm_errors all (0).
     - Fill up to n from rule_tagged and llm_unconditioned.
     - Inside each bucket, take ≥ 30% ERICA where the bucket has enough ERICA chunks.
   - **Floors,** reported and failing if not met:
     - ≥ 15 chunks whose TEXT mentions TOPIK (whatever was predicted);
     - ≥ 20 `rule_unconditioned`;
     - ≥ 4 chunks with predicted `any_of`.
   - **Writes:**
     - `OUT/blind_inputs.jsonl`: `chunk_id`, `site`, `title`, `heading_path`, `post_date`,
       `text`. **No predicted tags, bucket, method or condition status.**
     - `OUT/sample_meta.json`: `index_id`, seed, the chunk_id list, the bucket and campus of each
       chunk (kept out of the blind file), the achieved strata, and the index's full bucket
       partition from the manifest.
   - Refuse to overwrite either file unless `--force`.
2. **`compare --index-id ID --reference OUT/reference.jsonl`.** Reads the predicted tags from
   MongoDB at this moment, by chunk_id.
   - **Validate the reference** against the format in the rules file:
     - v1 vocabulary values;
     - every non-campus value has an evidence quote that is a substring of the chunk text
       (whitespace-normalized);
     - any violation gives exit 2, with a list.
   - **Units.** Attributes are the 8 constraint attributes plus `campus`, `scope` and
     `effective_term`.
     - Values are compared at the value level: TP, FP, FN per attribute, as in `audit_tags`.
     - `any_of` sets are expanded into their attribute values and counted under the attribute,
       and are also reported as a chunk-level exact-match rate.
   - **Splits:**
     - by method: rule vs llm (the predicted field's `extraction_method`; an FN goes to the
       chunk's bucket family);
     - by bucket;
     - by campus.
   - **Metrics:**
     - Wilson 95% intervals on every precision and recall;
     - bucket-weighted recall, using the partition in `sample_meta.json`.
   - **Disagreements.** Write `OUT/disagreements.jsonl`, one row per (chunk, attribute) where the
     value sets differ:
     - `chunk_id`, the chunk text, the heading path, the attribute;
     - `value_a` / `value_b` (the predicted and reference values in a seeded random order per row)
       and `evidence_a` / `evidence_b`.

     The key telling which side is which goes only into `OUT/disagreements_key.json`. It is never
     given to the reviewer.
   - Write `OUT/scores_raw.json` and `.md`.
3. **`finalize --index-id ID --reference … --decisions OUT/decisions.jsonl`.**
   - The reviewer's decision rows are `{chunk_id, attribute, decision: a|b|both_wrong|ambiguous,
     correct_values?, reason}`. Map them back through the key.
   - Build the final reference:
     - the reference side wins where the decision names it;
     - the predicted side wins where the decision names it;
     - `both_wrong` uses `correct_values`;
     - `ambiguous` rows are left out of the counts and listed.
   - Re-score as in `compare`, and write `OUT/scores_final.json`.
   - Write `OUT/scores_final.md` with the G2 table. One row per attribute with ≥ 5 occurrences,
     with these columns:
     - occurrences;
     - precision with its CI;
     - raw recall with its CI;
     - weighted recall with its CI;
     - pass/fail, where pass = precision ≥ 0.8 AND weighted recall ≥ 0.7.

     Below it, add the rule/llm, bucket and campus splits. Then add:
     - how many disagreements went to each side, and how many were ambiguous;
     - the most frequent `out_of_vocabulary_condition` texts;
     - the `audience` and `topik_scope` counts.

     The **limitation line** from the rules file comes first in the file.

Tests that must pass (offline; mongomock with a synthetic r3-like index of about 60 chunks in the
real chunk structure, per A1):
- sampling meets every floor and quota, is seeded, and `blind_inputs.jsonl` contains no key named
  `applicability`, `tag_bucket`, `condition_status` or `extraction_method`;
- compare on a hand-made 4-chunk reference has hand-computed TP/FP/FN in the docstring, including
  one `any_of` chunk and one rule-vs-llm split;
- the disagreement order is shuffled, and the key maps back correctly;
- finalize applies a, b, both_wrong and ambiguous as specified;
- the reference validator rejects a value outside v1 and a quote that is not in the text;
- all existing suites: `cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests`,
  and `cd Sources/backend && pytest -q`.

Human runs: nothing.

Done when: AGENTS.md Definition of done is met, and `T10c.result.md` has the exact command sequence.
