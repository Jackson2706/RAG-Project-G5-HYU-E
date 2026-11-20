# T43 — Runner: case-major order and a hard stop time for HYU runs
Owner: Codex (gpt-6.1-sol) · Reviewer: Claude Code · Phase: deck v5 Phase 3 preparation

Goal: the held-out run must run every method on one question before the next question, and stop at a fixed
deadline, so an early stop leaves balanced results (same questions for every method).

Read first: AGENTS.md; Sources/evaluation/runner.py (`run_hyu_task`, `main_async`, argument parser, status
handling); Sources/evaluation/guard.py; existing runner tests in Sources/evaluation/tests/.
Allowed write paths: Sources/evaluation/runner.py, Sources/evaluation/tests/test_runner_case_major.py (new),
Sources/docs/agent_tasks/T43.result.md.
Do not touch: guard.py rules, labels, configs, any other file. Do not commit or push.

Spec:
- New flags for `--suite hyu`: `--case-major` and `--stop-at <ISO 8601 with offset, e.g. 2026-11-21T12:00:00+09:00>`.
- With `--case-major`: the hyu tasks of the run share one loop: for each case (in `load_cases` order), run each
  ready task (preset order as planned) that has no record for that case yet, appending to that task's raw file
  exactly as `run_hyu_task` does today (same record, same resume rule via read_done). Reuse the per-case code of
  `run_hyu_task` (factor it into one helper used by both paths); the default (preset-major) path must not change.
- `--stop-at`: checked before each case starts (never in the middle of a case). When the time has passed, stop the
  loop, print "STOP_AT reached after N complete cases", mark each unfinished task's status "STOPPED" with
  `{"queries": n, "stopped_at": iso}`, still write reports, and exit 0. Also valid without --case-major (checked
  before each case of each task).
- A case whose every task already has a record is skipped quickly (resume).
- Status per task at the end: COMPLETED if all cases have records, else STOPPED.
- Tests (no Ollama/DB: monkeypatch the per-case helper / run_rag with a fake): case-major order is
  case1:[A,B], case2:[A,B]; resume skips done (case, preset) pairs; --stop-at in the past runs no case; a stop
  between cases leaves every task with the same number of records; preset-major default unchanged.

Verify with: cd Sources && pytest -q evaluation/tests ; python -m evaluation.runner --suite hyu --split dev --dry-run
Done when: AGENTS.md Definition of done items 1, 2, 5.
