# T01 — Move tracked files into Sources/ data/ results/ Report/
Owner: Codex · Reviewer: Claude Code · Phase: P1

Goal: Pure moves, PLAYBOOK.md Appendix A.1. No content edits except none needed to keep tests importable (T02 fixes paths).
Read first: AGENTS.md (layout), PLAYBOOK.md Appendix A.1.
Allowed write paths: tracked files listed in A.1 and their destinations; `Sources/docs/agent_tasks/T01.result.md`; `STATUS.md`.
Do not touch: `.claude/`, `.env`, `backend/.env`, `.run/`, `frontend/node_modules/`, `evaluation/datasets/`, any untracked file, `Sources/docs/agent_tasks/` (already exists), `AGENTS.md`, `CLAUDE.md`, `PLAYBOOK.md`.
Spec:
- CURRENT STATE (attempt 2): a first run already copied all 188 tracked files to their A.1 destinations (verified identical by `git hash-object`), but the old tracked copies are present again at the old paths. Your job now: for each `git ls-files` path in the A.1 sources, check that the destination exists with the same `git hash-object` as the index entry, then `rm` the old copy (plain rm; `.git` is read-only). Remove now-empty old directories only if they contain no untracked/ignored files. Never remove a file whose destination is missing or differs: list it in the result note instead.
- Move ONLY files from `git ls-files`. Use `git mv`; if `.git` is not writable in your sandbox, use plain `mv` of tracked files (the reviewer stages with `git add -A`). Never move untracked/ignored files (e.g. `evaluation/results/main/raw/`, `evaluation/datasets/`, `__pycache__`).
- `Sources/docs/` already exists: move `docs/*.md` into it, do not nest `Sources/docs/docs`.
- Mapping (A.1): `backend/`→`Sources/backend/`, `frontend/`→`Sources/frontend/`, `evaluation/` (tracked, except results/main and annotations)→`Sources/evaluation/`, `evaluation/results/main/*`→`results/2026-11-01_main/`, `evaluation/annotations/*`→`data/HYU/labels/legacy/`, `scripts/`→`Sources/scripts/`, `docs/*.md`→`Sources/docs/`, `data/samples/*`→`data/HYU/synthetic_fixture/`, `data/eval/sample_questions.jsonl`→`data/HYU/labels/legacy/`, `data/raw/README.md`→`data/HYU/README.md`, `docker-compose.yml setup.sh start.sh stop.sh uninstall.sh .env.example`→`Sources/`. `README.md`, `.gitignore` stay at root.
- Check name collisions in `data/HYU/labels/legacy/` (two README.md would collide: if so keep annotations' as `README.md`).
Tests that must pass: none yet (paths break until T02). Run them anyway and report the failures in the result note.
Verify with: `git status --short | head -50`, `find Sources data results -maxdepth 3 -type d | sort`.
Human runs: nothing.
Done when: every tracked file is at its A.1 destination; untracked files untouched; `T01.result.md` lists moves, collisions, and the test output; one STATUS.md line.
