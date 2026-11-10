# T06b — Benchmark loader fixes: real-schema fixtures and real-data smoke tests
Owner: Codex · Reviewer: Claude Code · Phase: P3

Goal: Loading the real files shows two bugs in `conditionalqa.py`, and the T06 fixtures do not match
the real file structure. Fix them per PLAYBOOK Amendment A1.

Read first: AGENTS.md, PLAYBOOK "Amendments" (A1), `Sources/evaluation/conditionalqa.py`,
`Sources/evaluation/scifact_original.py`, `Sources/evaluation/tests/test_benchmark_adapters.py`
and its fixtures.

Allowed write paths: `Sources/evaluation/conditionalqa.py`, `Sources/evaluation/scifact_original.py`,
`Sources/evaluation/tests/` (the adapter tests and fixtures), `Sources/docs/agent_tasks/T06b.result.md`.
Do not touch: `Report/`, `beir.py` checksums, the runner.

Real schema (Claude Code inspected the downloaded files on 2026-11-10):

| File | Top level | Fields (all present in every row unless noted) |
|---|---|---|
| conditionalqa `train.json`, `dev.json` | list (2,338 / 285) | `id` str ("dev-0"), `url` str, `scenario` str, `question` str, `not_answerable` bool, `answers` list of 2-item lists `[answer: str, conditions: list[str]]`, `evidences` list[str] (raw HTML elements) |
| conditionalqa `test_no_answer.json` | list (804) | `id`, `url`, `scenario`, `question` only; **no** `not_answerable`, `answers`, `evidences` |
| conditionalqa `documents.json` | **list** (652) | `title` str, `url` str, `contents` list[str] (one raw HTML element each: `<h1>…</h1>`, `<p>…</p>`, `<li>…</li>`, `<tr>…</tr>`, …) |
| scifact_original `claims_train/dev.jsonl` | JSONL (809 / 300) | `id` int, `claim` str, `evidence` dict {doc_id str: [{"sentences": [int], "label": "SUPPORT"\|"CONTRADICT"}]} (may be `{}`), `cited_doc_ids` list[int] |
| scifact_original `claims_test.jsonl` | JSONL (300) | `id` int, `claim` str only |
| scifact_original `corpus.jsonl` | JSONL (5,183) | `doc_id` int, `title` str, `abstract` list[str] (sentences), `structured` bool |

Spec:
1. `conditionalqa.load_questions("test")` works on the real test file. `not_answerable`, `answers`
   and `evidences` are `None` for test rows. They are never `False` or `[]` (A1: a missing label
   stays None). Train/dev keep the T06 types.
2. `conditionalqa.load_documents()` reads the list and returns {url: {"title", "contents"}}. Raise a
   clear error on a duplicate url.
3. SciFact: check `load_claims`/`load_corpus` against the table. If corpus `doc_id` is int, keep str
   keys in the returned dict (cited ids are converted the same way), and say so in a docstring.
4. Rebuild every adapter fixture so its structure is exactly the real one in the table: same
   top-level type, keys, value types, and the missing fields in test files. Use synthetic content
   (invented text). For each dataset, include one row of every shape the table lists. Examples:
   - an answer with conditions and one without;
   - a `not_answerable` question;
   - a claim with `evidence: {}`;
   - a document with `<h2>` and `<li>` elements.
5. Real-data smoke tests, one per dataset (scifact, nfcorpus, arguana via `beir.load`, plus
   scifact_original and conditionalqa):
   - each loads the actual file from `DATA_DIR/benchmarks/<name>/`;
   - each is skipped with a clear reason when the file is absent;
   - each asserts only stable facts: row counts from the table, types, and that every test-split
     label is None;
   - for conditionalqa, `to_parsed_documents(load_documents())` runs, and every document has ≥ 1
     section.
6. In `T06b.result.md`, report:
   - the ConditionalQA document count;
   - total sections, and min / median / max sections per document;
   - whether the official `evaluate.py` exists at the pinned commit
     `77bd295952daf415548b3244db10880d3d55cfe0` (in the repo root, per its README). Don't download
     it, just say it is needed for A3.

Tests that must pass: the adapter tests including the new smoke tests, plus all existing suites:
backend (`cd Sources/backend && pytest -q`; `tests/test_applicability.py` is a new
tests-first file and is expected to fail until T08, so ignore it), and
`cd Sources && pytest -q evaluation/tests crawler/tests`.

Verify with: the commands above and `python -m evaluation.runner --suite all --dry-run`. The
smoke tests read local files only, so they are fine to run.

Human runs: nothing.

Done when: AGENTS.md Definition of done is met, and `T06b.result.md` has the counts from item 6.
