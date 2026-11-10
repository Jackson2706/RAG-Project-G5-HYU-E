# T07 — SciFact mapping check: BEIR test queries → original claims
Owner: Codex · Reviewer: Claude Code · Phase: P3

Goal: Build a script that checks whether the BEIR SciFact test query IDs are the original SciFact
**dev** claims, and reports their SUPPORT/CONTRADICT/NEI counts. If they are, the BEIR retrieval
benchmark gets claim labels for sufficiency and abstention experiments.

Read first: AGENTS.md, `Sources/evaluation/beir.py` (`load`), `Sources/evaluation/scifact_original.py`
(from T06).

Allowed write paths:
- new `Sources/evaluation/scifact_mapping.py`;
- new `Sources/evaluation/tests/test_scifact_mapping.py` (reuse the T06 fixtures folder);
- `Sources/docs/06_BENCHMARK_AND_EVALUATION.md` (a short section);
- `Sources/docs/agent_tasks/T07.result.md`.

Do not touch: `Report/` (the human or Claude Code runs the script), `beir.py`,
`scifact_original.py`, the runner.

Spec: `python -m evaluation.scifact_mapping [--beir-split test] [--orig-split dev] [--out DIR]`
1. Load the BEIR queries and qrels: `beir.load("scifact", beir_split)`. Use only the queries dict
   and the qrels. Do not build an index.
2. Load the original claims: `scifact_original.load_claims(orig_split)`.
3. For every BEIR query ID, compare it with the original claim IDs, matching `str(int)` against the
   original's `str(id)`. Report:
   - `n_beir_queries`, `n_orig_claims`, `n_id_matched`, and `unmatched_ids` (the first 20);
   - `n_text_equal`: claim text identical after `strip()` and whitespace collapsing;
     `text_mismatch_examples`: up to 5 `{id, beir, orig}`;
   - `label_counts` over the matched claims: SUPPORT / CONTRADICT / NEI / MIXED;
   - `qrels_vs_evidence`: for the matched claims, the number where the BEIR qrels doc set
     - equals the evidence doc set;
     - is a superset of it;
     - is a subset of it;
     - is something else.

     Also count NEI claims that have qrels, and say whether BEIR qrels come from the evidence or
     from `cited_doc_ids`: report `n_qrels_equal_cited` too.
   - `orig_claims_missing_from_beir`: the count, and that count split by label.
4. Output:
   - print a small Markdown table;
   - write `<out>/mapping.json`, the full report plus input SOURCE checksums (BEIR md5,
     scifact_original md5);
   - write `<out>/mapping.md`.

   Default `--out` = `RESULTS_DIR / "scifact_mapping"`. These files are small summaries, safe to
   commit. Never write per-claim text dumps beyond the 5 examples.
5. A missing dataset gives a clear error that names the `--download` command (exit 2, no traceback).

Tests that must pass (`test_scifact_mapping.py`). Use a tiny BEIR-format fixture and an original
fixture with:
- one matched SUPPORT claim whose qrels equal its evidence;
- one matched NEI claim that has qrels equal to its cited docs;
- one BEIR ID missing from the original;
- one original claim missing from BEIR.

Assert every count above on this fixture. Use monkeypatched folders under `tmp_path`.
All existing suites still pass.

Verify with:
```
cd Sources && pytest -q evaluation/tests
python -m evaluation.runner --suite all --dry-run
```

Human runs: nothing new. Claude Code runs `python -m evaluation.scifact_mapping` after the T06
downloads. It is offline and fast.

Done when: AGENTS.md Definition of done is met, and `T07.result.md` is written.
