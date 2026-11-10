# T10 — Applicability tag audit: sample, sheet, scores, frequency table
Owner: Codex · Reviewer: Claude Code · Phase: P4 (→ Gate G2)

Goal: Measure the precision and recall of the AAES chunk tags on the published index
`hyu_20261110_97dc1269_r1`. Write a stratified 50-chunk audit sheet that the team fills in by hand,
then score it per attribute AND per extraction method. Also write the attribute-frequency table
over all chunks, which is the input for vocabulary v1.

Read first:
- AGENTS.md, and PLAYBOOK "Amendments" A5, A6, A7, A8;
- `Sources/backend/app/rag/applicability.py`;
- `Sources/backend/app/rag/snapshot.py`;
- `Sources/backend/app/database.py` (`for_index`);
- `Report/results/index_reports/hyu_20261110_97dc1269_r1.md`.

Allowed write paths:
- new package `Sources/labeling/` (`__init__.py`, `audit_tags.py`, `tests/`);
- `Sources/docs/aaes_spec.md` (a short "Tag audit" section);
- `Sources/docs/agent_tasks/T10.result.md`.

Do not touch:
- `Report/` (Claude Code runs the commands);
- the index;
- the tagger and the vocabulary.

Data per chunk, as stored in MongoDB (`hyu_bench_hyu_20261110_97dc1269_r1`, collection `chunks`):
- `chunk_id`, `doc_id`, `text`, `section`;
- `applicability`: a `ChunkCondition.to_dict()` with `constraints`, `scope`, `campus`,
  `requirements`, `effective_term`, `superseded_by`, `extraction_method` and `evidence`;
- `tag_bucket` (one of the six in A6), `condition_status` (`conditioned` | `unconditioned` |
  `unknown`), and `source_spans` (snapshot `[start, end]` pairs).

The documents collection has `doc_id`, `source_uri`, `title` and `metadata.campus` / `site`. The
span kind (table_row etc.) comes from the snapshot `documents.jsonl`: match the chunk's
`source_spans` to the row's `spans` by offsets.

Audited attributes: the 7 constraint attributes (`degree_level`, `year`, `student_type`, `visa`,
`topik_level`, `english_track`, `academic_status`), plus `campus` and `effective_term`.

CLI (`python -m labeling.audit_tags <command>`, run from `Sources/`):

1. **`sample --index-id ID --n 50 --seed 20261110 [--out Report/notes/tag_audit.csv]`**
   - Draw a seeded, stratified sample. Each constraint below is a floor:
     - 25 Seoul and 25 ERICA (by the document's site);
     - ≥ 20 with `condition_status == "conditioned"`;
     - ≥ 5 table-row chunks (every covered span is a `table_row`);
     - ≥ 8 `rule_unconditioned`, ≥ 5 `llm_unconditioned`, ≥ 3 `llm_rejected` (unknown);
     - ≥ 10 with at least one LLM-extracted field.
   - Use a simple greedy method: fill the floors first, in a fixed order, at random within each
     stratum, then fill up to 25 per campus at random. Print the achieved count per stratum, and
     fail if a floor cannot be met.
   - One CSV row per chunk. Columns, in order:
     - `chunk_id`, `campus`, `source_uri`, `kind`, `tag_bucket`, `condition_status`, `section`,
       `text` (the full chunk text);
     - then for each audited attribute A: `A_pred` (values joined with `|`), `A_method` (`rule`,
       `llm`, `site_default` or `snapshot`), `A_correct`, `A_wrong`, `A_missed` (the last three
       empty);
     - then `reviewer`, `notes`.
   - Refuse to overwrite an existing CSV unless `--force`. Humans will be editing it.
2. **`score --csv Report/notes/tag_audit.csv [--out Report/results/tag_audit/<index_id>/]`**
   - **Filling rules.** A row is reviewed when `reviewer` is non-empty. For a reviewed row and each
     attribute:
     - every value in `A_pred` appears in exactly one of `A_correct` / `A_wrong`;
     - `A_missed` lists true values the tagger did not predict;
     - all values are in the vocabulary (`effective_term` must match `TERM_RE`).

     Violations are listed with row and attribute. A sheet with violations does not score; exit 2.
   - **Counts.** TP = |correct|, FP = |wrong|, FN = |missed|, at the value level. Per attribute,
     report TP, FP, FN, precision, recall, `occurrences`, and `gated`.
     - `occurrences` = the number of reviewed chunks where the attribute is predicted or missed;
     - `gated = occurrences ≥ 5` (A5);
     - a 0/0 precision or recall is reported as null, never as 0 or 1.
   - **Splits.**
     - By extraction method: rule vs llm. Count TP/FP under `A_method`. FN go to the method of the
       chunk's bucket (`rule_*` → rule, `llm_*` → llm).
     - By bucket.
     - By campus.
   - **Unknown chunks** (`llm_rejected`): report their count and how many had any `A_missed`.
   - **G2 verdict:** for each gated attribute, precision ≥ 0.8 AND recall ≥ 0.7. List each failing
     attribute.
   - Write `scores.json` and `scores.md`.
3. **`frequency --index-id ID [--out Report/results/tag_audit/<index_id>/frequency.md|json]`**
   - Over ALL chunks: count per `attribute=value`, split by method (rule / llm) and by campus.
   - List every vocabulary value never seen (a v1 candidate to drop) and the 15 most frequent
     requirement phrases (a candidate for new attributes).
   - Read the index from MongoDB with `Database.connect(get_settings()).for_index(ID)`.

Tests that must pass (`Sources/labeling/tests/`, offline):
- **Sampling:** use mongomock with a synthetic index (about 80 chunks covering every stratum).
  - Every floor is met, the sample is the same for the same seed, and the CSV columns are in order.
  - When a stratum is too small, the command fails with a clear message.
  - It refuses to overwrite.
- **Scoring:** a hand-made 4-row sheet with hand-computed precision and recall, written in the test
  docstring.
  - The rule/llm split and the bucket split are checked against the same hand computation.
  - A missed value on an `llm_unconditioned` row counts as an LLM FN.
  - A 0/0 metric gives null.
  - A violation gives exit 2 and names the row and attribute.
- **Frequency:** counts and the "never seen" list on the synthetic index.
- All existing suites still pass: backend 136, evaluation + crawler 87.

Verify with:
```
cd Sources && pytest -q labeling/tests evaluation/tests crawler/tests
cd Sources/backend && pytest -q
cd Sources && python -m evaluation.runner --suite all --dry-run
```

Claude Code runs these (local MongoDB, read-only, fast):
```
python -m labeling.audit_tags sample --index-id hyu_20261110_97dc1269_r1 --n 50 --seed 20261110
python -m labeling.audit_tags frequency --index-id hyu_20261110_97dc1269_r1
```
The human team fills in the sheet. Then Claude Code runs `score`.

Done when: AGENTS.md Definition of done is met, and `T10.result.md` gives the commands and the
filling instructions for the team, in five plain lines with one example row.
