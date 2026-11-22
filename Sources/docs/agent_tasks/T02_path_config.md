# T02 — Central path config after the reorg
Owner: Codex · Reviewer: Claude Code · Phase: P1

Goal: Make everything work from the new layout, PLAYBOOK.md Appendix A.2. All paths resolve in `Sources/backend/app/config.py`.
Read first: AGENTS.md, PLAYBOOK.md Appendix A.2, `Sources/docs/agent_tasks/T01.result.md`, `Sources/backend/app/config.py`, `Sources/evaluation/{beir,runner}.py`.
Allowed write paths: `Sources/**` (code, tests, docs, shell scripts, `.env.example` files), `README.md`, `.gitignore`, `.gitkeep` files under `data/` and `Report/`, `T02.result.md`, `STATUS.md`.
Do not touch: `.claude/`, `results/2026-11-01_main/`, `data/HYU/labels/legacy/`, `data/HYU/synthetic_fixture/` contents, any `.env`, AGENTS/CLAUDE/PLAYBOOK.md.
Spec:
- `config.py`: `BACKEND_DIR` (unchanged meaning), `PROJECT_ROOT = BACKEND_DIR.parent` (= `Sources/`, keep name), `REPO_ROOT = PROJECT_ROOT.parent`, `DATA_DIR`, `RESULTS_DIR`, `REPORT_DIR` defaulting to `REPO_ROOT/{data,results,Report}`, overridable by env `HYU_DATA_DIR`, `HYU_RESULTS_DIR`, `HYU_REPORT_DIR` (read at import, `Path(os.environ.get(...))`). `Settings.data_dir` defaults to `DATA_DIR`.
- `evaluation/beir.py`: `DATASETS_DIR = DATA_DIR / "benchmarks"`. `evaluation/runner.py`: `RESULTS_DIR` from config; update `--run-id` help and docstrings (`results/<run-id>/`). Default run id stays `main`/`smoke`. Configs dir stays `Sources/evaluation/configs`.
- Any other hard-coded `data/samples`, `data/eval`, `evaluation/annotations`, `evaluation/results`, `evaluation/datasets` path (code, tests, fixtures, scripts, frontend text, docs) → new location. Ingest API `folder` is relative to `DATA_DIR`: default `"HYU/raw"`, description examples `'HYU/raw'` or `'HYU/synthetic_fixture'`.
- `docker-compose.yml` keeps `name: hyu-compass` and its volume names unchanged. Shell scripts still `cd` to their own folder (`Sources/`); fix relative paths inside them (`backend/`, `frontend/`, `.env`, `.run/`).
- `.gitignore`: exactly the A.2 list, plus keep existing generic rules (pycache, logs, OS files, `.claude`, embedded qdrant now `Sources/backend/qdrant_data/`, `Sources/frontend/*.tsbuildinfo`). Old root-level paths removed.
- `.gitkeep` in `data/HYU/snapshots`, `data/HYU/labels`, `Report/{report,slides,figures,tables,notes}`.
- README.md + `Sources/docs/*`: layout tree and commands (`cd Sources && python -m evaluation.runner ...`, `cd Sources/backend && pytest -q`).
- One small test in `Sources/backend/tests/` : env overrides change `DATA_DIR`/`RESULTS_DIR`/`REPORT_DIR` (reload module with monkeypatched env) and defaults sit under `REPO_ROOT`.
Tests that must pass: `cd Sources/backend && pytest -q`; `cd Sources && pytest -q evaluation/tests`.
Verify with: the two pytest commands; `cd Sources && python -m evaluation.runner --suite all --dry-run` (no network needed); `grep -rn "evaluation/results\|evaluation/datasets\|data/samples" Sources README.md --exclude-dir=node_modules`.
Human runs: Appendix A.3 moves of untracked files; `./start.sh` from `Sources/`.
Done when: AGENTS.md Definition of done; dry-run lists 108 tasks; no stale old-path strings remain except in `results/2026-11-01_main/` (legacy, untouched).
