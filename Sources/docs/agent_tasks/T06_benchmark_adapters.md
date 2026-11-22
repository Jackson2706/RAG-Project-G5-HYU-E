# T06 — Benchmark adapters: SOURCE.md, original SciFact, ConditionalQA
Owner: Codex · Reviewer: Claude Code · Phase: P3

Goal: BEIR scifact/nfcorpus/arguana already live in `Report/data/benchmarks/<name>/` (loader:
`Sources/evaluation/beir.py`, checksums unchanged). Add a committed `SOURCE.md` to every dataset
folder, and add download + load adapters for two more datasets: the original SciFact release
(claims with labels and rationales) and ConditionalQA (eligibility questions with conditions).
No runner suite uses them yet. This task adds only loaders.

Read first: AGENTS.md, `Sources/evaluation/beir.py`, `Sources/evaluation/runner.py` (`main()`),
`Sources/evaluation/tests/test_runner.py`, `.gitignore` (benchmark rules).

Allowed write paths:
- `Sources/evaluation/beir.py` (SOURCE.md writer only, no loader or checksum changes);
- new `Sources/evaluation/scifact_original.py`, `Sources/evaluation/conditionalqa.py`;
- `Sources/evaluation/runner.py` (only the `--download` dispatch and its help text);
- new `Sources/evaluation/tests/test_benchmark_adapters.py` and tiny fixtures under
  `Sources/evaluation/tests/fixtures/benchmarks/`;
- `Sources/docs/06_BENCHMARK_AND_EVALUATION.md`;
- `Sources/docs/agent_tasks/T06.result.md`.

Do not touch: anything under `Report/` (the human runs the downloads), `.gitignore`, the BEIR
`DATASETS` checksums, the runner's tasks and configs.

Spec:
1. **SOURCE.md writer.** Add `write_source_md(folder: Path, source: dict) -> None` in `beir.py`. It
   writes `folder/SOURCE.md`, a short Markdown file with these fields: dataset, URL(s), licence,
   checksum type and value, whether the checksum was verified against a published value, the
   download date, splits, and one line on what the folder holds. Call it in:
   - `beir.download()`, also on the cached path. If `SOURCE.json` exists but `SOURCE.md` does not,
     write it, so `--download scifact,nfcorpus,arguana` backfills the three existing folders
     without network;
   - the two new download functions.
2. **`scifact_original.py`** → folder `DATA_DIR/benchmarks/scifact_original/`.
   - URL: `https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz`.
   - Expected md5: `cb7da4d8609e30f2c7483b61aa447f7e`, which is the S3 ETag of the single-part
     upload (Last-Modified 2021-01-26). Wrong md5 → delete the archive, unpack nothing, raise.
     Record sha256 as well.
   - Unpack into the folder only these files, flattened (no `data/` prefix): `claims_train.jsonl`,
     `claims_dev.jsonl`, `claims_test.jsonl` and `corpus.jsonl`. Skip the cross-validation folds,
     and refuse any member whose path is absolute or contains `..`.
   - Licence: claims and evidence annotations CC BY 4.0, abstracts ODC-By 1.0 (S2ORC), from
     github.com/allenai/scifact LICENSE.md.
   - `load_claims(split) -> list[dict]`. Each dict has these keys:
     - `id` (int);
     - `claim`;
     - `cited_doc_ids` (list of str);
     - `evidence`: {doc_id: {"label": "SUPPORT"|"CONTRADICT", "sentences": sorted unique ints}}.
       Merge the rationale sets of a document. Raise if one document has both labels;
     - `label`: `"NEI"` if `evidence` is empty, the single label if all documents agree, else
       `"MIXED"`.

     `split="test"` raises ValueError("SciFact test claims are unlabeled").
   - `load_corpus() -> dict[str, dict]`: {doc_id: {"title", "sentences": list[str]}}.
3. **`conditionalqa.py`** → folder `DATA_DIR/benchmarks/conditionalqa/`.
   - Base URL pinned to commit `77bd295952daf415548b3244db10880d3d55cfe0`:
     `https://raw.githubusercontent.com/haitian-sun/ConditionalQA/<commit>/v1_0/{train,dev,test_no_answer,documents}.json`.
   - There is no published checksum. The first download records sha256 per file (`verified: false`,
     "pinned commit, sha256 recorded on first download"). If `SOURCE.json` already lists a sha256
     for a file, a later download must match it.
   - Licence: BSD 2-Clause (repo file `LISCENSE`), plus the README disclaimer "This dataset should
     ONLY be used for NLP research purpose." Both go into SOURCE.md.
   - `load_questions(split)` for `train` and `dev`. Each item has these keys:
     - `id`, `url`, `scenario`, `question`;
     - `not_answerable` (bool);
     - `answers`: list of {"answer": str, "conditions": list[str]};
     - `evidences` (list[str]).

     `split="test"` returns the questions with `answers=[]` and `evidences=[]`, and logs that test
     answers are not public.
   - `load_documents() -> dict[url, dict]` with `title` and `contents` (list of raw HTML strings),
     as published.
   - `to_parsed_documents(docs) -> list[ParsedDocument]`:
     - `source_uri = "conditionalqa://" + url`, `file_type = "conditionalqa"`;
     - a new Section starts at each `<h1>`–`<h4>` element (heading text = tag text);
     - every other element is tag-stripped text appended to the current section;
     - use `html.parser` from the stdlib (or bs4 if already installed in the env; check
       `Sources/backend/requirements.txt`);
     - a `condition` is the plain text of the HTML element the paper points to. Keep it as is.
4. **Runner.** `--download` accepts a comma list of any of
   `scifact,nfcorpus,arguana,scifact_original,conditionalqa`. Map each name to its module's
   `download()` and keep the BEIR names going to `beir.download`. The help text names the
   destination `Report/data/benchmarks/`.
5. **Downloads.** Use only `urllib` (no new dependency). Use a 120 s timeout and a generic
   User-Agent (`hyu-compass-benchmarks/1.0`), with no personal data in it. Write each file to a
   `.part` file first and rename it after its checksum passes.

Tests that must pass. Add `test_benchmark_adapters.py`, offline only, with tiny hand-made fixtures
of 2–3 records each in the real format:
- SciFact: one claim with a SUPPORT label, one CONTRADICT, one NEI, and one claim whose two
  evidence documents disagree (`label == "MIXED"`). Rationale sets of one document are merged and
  sorted. `load_claims("test")` raises.
- Tar safety: an archive member named `../evil` is refused. Build the archive with `tarfile` in
  `tmp_path`.
- Checksum: the wrong md5 raises, and no claim files appear in the folder. Monkeypatch the fetch;
  no network.
- ConditionalQA: one answerable question with one condition, and one `not_answerable` question.
  `to_parsed_documents` splits `<h2>A</h2><p>x</p><h2>B</h2><li>y</li>` into two sections, A:"x"
  and B:"y".
- `write_source_md` writes the licence and checksum lines. The BEIR cached path backfills SOURCE.md
  from an existing `SOURCE.json` in `tmp_path` (monkeypatch `DATASETS_DIR`).
- Point the modules at `tmp_path` by monkeypatching their folder constant. Never write under
  `Report/`.
- All existing suites still pass: backend 95, evaluation 22, crawler 48.

Verify with:
```
cd Sources/backend && pytest -q
cd Sources && pytest -q evaluation/tests crawler/tests
python -m evaluation.runner --suite all --dry-run
```

Human runs (the agent must NOT run these):
```
cd Sources && conda activate RAG
python -m evaluation.runner --download scifact,nfcorpus,arguana      # no network: backfills SOURCE.md
python -m evaluation.runner --download scifact_original,conditionalqa
```

Done when: AGENTS.md Definition of done is met (no UI change, so no frontend checks), and
`T06.result.md` lists every file changed, anything skipped, and the exact human commands.
