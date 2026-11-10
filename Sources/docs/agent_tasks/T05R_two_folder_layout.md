# T05R — Two-folder layout: paths, ignore rules, docs
Owner: Codex · Reviewer: Claude Code · Phase: P2 (cleanup)

Goal: The folders have already been moved (by Claude Code, with `mv` / `git mv`):
`data/` → `Report/data/`, `results/` → `Report/results/`, `PLAYBOOK.md` and `STATUS.md` →
`Report/project/`. `.gitignore` is already updated. Make code, tests and docs match the new layout.
The root keeps only `Sources/`, `Report/`, `README.md`, `AGENTS.md`, `CLAUDE.md` and hidden files.

Read first: AGENTS.md, `Sources/backend/app/config.py`, `Sources/docs/agent_tasks/T05R.before.md`.

Allowed write paths:
- `Sources/` (code, tests, docs, scripts; not `Sources/docs/agent_tasks/T0[1-5]*`);
- `AGENTS.md`, `CLAUDE.md`, `README.md`;
- `Report/project/PLAYBOOK.md`;
- `Report/data/HYU/README.md`;
- `Sources/docs/agent_tasks/T05R.result.md`.

Do not touch:
- anything else under `Report/data/` or `Report/results/`, and never rewrite or regenerate
  `Report/data/HYU/manifest.jsonl` or `Report/data/HYU/snapshots/**`: the snapshot id depends on the
  manifest SHA;
- `Report/project/STATUS.md` (Claude Code updates it);
- `.gitignore`;
- the untracked root leftovers `backend/`, `frontend/`, `evaluation/`, `Reports/`.

Spec:
1. `config.py`:
   - `DATA_DIR = REPORT_DIR / "data"` and `RESULTS_DIR = REPORT_DIR / "results"`;
   - define `REPORT_DIR` first;
   - keep the env overrides `HYU_DATA_DIR`, `HYU_RESULTS_DIR` and `HYU_REPORT_DIR`. When only
     `HYU_REPORT_DIR` is set, data and results follow it.
2. Grep `Sources/` (excluding `node_modules`, `.run`, `tests/fixtures`) for literal `data/` and
   `results/` paths.
   - Code must use the config constants.
   - User-facing text (help strings, error messages, UI labels, comments) names the new locations,
     e.g. `Report/data/` or "a folder under the data directory".
   - The Docker path `/data/db` in docker-compose.yml is unrelated. Leave it.
3. Stored relative paths:
   - Manifest and snapshot paths are relative to `DATA_DIR` (`HYU/raw/...`); they need no change.
   - Run manifests in `Report/results/*/run_manifest.json` store repo-relative paths from older
     layouts, e.g. `data/eval/...` and `evaluation/annotations/...`. Do not rewrite them.
   - `evaluation/reports.py` (around line 428) resolves `annotations` against `REPO_ROOT`. Add one
     small helper in config.py, `resolve_stored_path(p)`:
     - `data/...` → `DATA_DIR / rest`;
     - `results/...` → `RESULTS_DIR / rest`;
     - any other relative path → `REPO_ROOT / p`;
     - absolute paths unchanged.
   - Use it there. If the resolved file does not exist, keep today's behaviour, which is answer
     metrics N/A.
4. Synthetic fixture: the app uses it (setup.sh ingest, `ConfigurationTab.tsx`, `api.py`, the
   evaluation runner).
   - It stays at `Report/data/HYU/synthetic_fixture`, reached through `DATA_DIR`
     (`HYU/synthetic_fixture`).
   - Only docs and messages change.
5. Docs: update path references in:
   - `AGENTS.md` (the repository layout block);
   - `CLAUDE.md`;
   - `Report/project/PLAYBOOK.md`;
   - `Sources/docs/*.md` (not the agent_tasks history files);
   - `Sources/evaluation/fixtures/README.md`;
   - `Report/data/HYU/README.md`;
   - `Sources/uninstall.sh` messages;
   - the help texts of the crawler and evaluation CLIs.

   `AGENTS.md` and `CLAUDE.md` must point to `Report/project/PLAYBOOK.md` and
   `Report/project/STATUS.md`. The do-not-commit list becomes `Report/data/HYU/raw/`, benchmark
   files, `Report/course/`, `.env` files and large per-query raw results.
6. Do NOT rewrite README.md beyond its path references. Claude Code rewrites it after review.

Tests that must pass (add the first three):
- `Sources/backend/tests/test_config_paths.py`:
  - with no env vars, `DATA_DIR == REPORT_DIR / "data"`, `RESULTS_DIR == REPORT_DIR / "results"`,
    and `REPORT_DIR == REPO_ROOT / "Report"`;
  - `resolve_stored_path("data/HYU/x")` returns `DATA_DIR / "HYU/x"`;
  - `resolve_stored_path("results/r/a")` returns `RESULTS_DIR / "r/a"`;
  - `resolve_stored_path("evaluation/x")` returns `REPO_ROOT / "evaluation/x"`.
- `Sources/crawler/tests/test_committed_snapshot.py`: loads the real committed snapshot at
  `DATA_DIR / "HYU/snapshots/hyu-20261110-97dc1269"`.
  - Verify every line in `SNAPSHOT.sha256` against the files.
  - Check that `documents.jsonl` has 362 rows and that each row has `doc_id` and `text`.
  - Check that the snapshot id suffix equals the first 8 hex of sha256(`DATA_DIR/HYU/manifest.jsonl`).
  - Skip with a clear reason if the snapshot directory is missing (e.g. an `HYU_DATA_DIR`
    override).
- A test that `crawler.run --dry-run` still works. The existing one in test_cli.py is enough if
  it passes.
- All existing suites: backend 90, evaluation 22, crawler 47 (plus the new ones).

Verify with:
```
cd Sources/backend && pytest -q
cd Sources && pytest -q evaluation/tests crawler/tests
python -m evaluation.runner --suite all --dry-run
python -m crawler.run --site all --dry-run
cd frontend && npm run typecheck && npm test
```
Run `grep -rnE "(^|[^/A-Za-z])(data|results)/" Sources --include='*.py' --include='*.sh' --include='*.ts' --include='*.tsx'`.
Every hit left must be justified in the result note.

Human runs: nothing (Claude Code restarts the app and checks the UI).

Done when: AGENTS.md Definition of done, plus the checks above. `T05R.result.md` lists every file
changed, every grep hit kept and why, and anything you skipped.
