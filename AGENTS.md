# AGENTS.md — HYU Compass (shared rules for Codex and Claude Code)

Codex reads this file directly. Claude Code reads it through `CLAUDE.md` (`@AGENTS.md`).
If a rule here conflicts with a skill (Ponytail, Humanizer), this file wins.

## What this project is

HYU Compass is a modular RAG system that answers new Hanyang University students from official
English university pages, with source references. It is a course project for
"Design of Generative AI Application Systems" (Lessons 3–6).

Research contribution: **AAES — Applicability-Aware Evidence Sufficiency.** Evidence counts as
sufficient only if it answers the question *and* applies to the asking student (campus, degree
level, year, student type/visa, language status, academic status, term). Otherwise the system
gives a conditional answer, asks one clarifying question, or abstains and refers the student to
the right office. Spec: `Sources/docs/aaes_spec.md`.

- Plan, phases, gates: `Report/project/PLAYBOOK.md`
- Progress log: `Report/project/STATUS.md`
- Task specs and results: `Sources/docs/agent_tasks/`

## Repository layout (all paths repo-relative)

```
AGENTS.md  CLAUDE.md  README.md
Sources/   ALL code: backend/ frontend/ evaluation/ crawler/ labeling/ scripts/ docs/
           docker-compose.yml  setup.sh  start.sh  stop.sh  uninstall.sh  .env.example
           data/HYU/    raw/ (gitignored) manifest.jsonl snapshots/<id>/ labels/
           data/benchmarks/<dataset>/   (gitignored except SOURCE.md)
           data/DATA.md  provenance and reproduction of all data
Report/    results/<run_id>/ per evaluation run, plus TEST_RUNS.md, index_reports/, tag_audit/
           project/PLAYBOOK.md project/STATUS.md
           report/ slides/ figures/ tables/ notes/ course/ (gitignored)
           voice_sample.md  ai_use_statement.md
```

Every path is resolved in ONE place: `Sources/backend/app/config.py`
(`REPO_ROOT`, `DATA_DIR`, `RESULTS_DIR`, `REPORT_DIR`, overridable with the env vars
`HYU_DATA_DIR`, `HYU_RESULTS_DIR`, `HYU_REPORT_DIR`). Never hard-code another absolute path.

## Environment

- macOS (Apple Silicon, 16 GB). Conda env `RAG`, Python 3.13. Reuse it. Never recreate it.
- MongoDB + Qdrant via `Sources/docker-compose.yml`. Its project name is fixed to `hyu-compass`,
  so the volumes are `hyu-compass_mongodb_data` and `hyu-compass_qdrant_data`.
- NEVER run `docker compose down -v`, delete Docker volumes, or drop databases/collections that
  the current task did not create.
- Ollama generation backbones: `llama2:7b`, `qwen3.5:4b`. Every run manifest records model digest,
  quantization, `num_ctx`, temperature, seed, and thinking mode.

## Architecture rules (do not break)

- One block = one folder with `base.py`. One method = one concrete subclass in its own file.
- `Sources/backend/app/rag/registry.py` is the single source of truth (methods, hyperparameters,
  presets, frontend metadata). Presets live in `presets.py`.
- One pipeline runner, shared by the app and the evaluator. The UI is for demos; experiments run
  headless through `python -m evaluation.runner` (from `Sources/`).
- No standalone online Citation Verification block. Claim support is offline evaluation only.
- No plugin frameworks, metaclasses, or speculative abstractions.
- The AAES attribute vocabulary lives only in `Sources/backend/app/rag/applicability.py`.

## UI and demo rules (the UI stays — it is our demo for the professor)

- Keep the React UI working after every task: the chat, the Configuration tab, and the Execution
  tab. Never remove or break an existing UI feature or API endpoint.
- **Every method we evaluate is also runnable from the UI.** Each existing baseline, each new
  baseline, each memory method, and each AAES variant and ablation is a preset in `presets.py`,
  validated by the registry. It therefore appears in the preset picker through
  `GET /api/pipeline/presets`. There are no evaluation-only code paths: the UI and the runner call
  the same pipeline.
- Each preset has three fields for the picker:
  - `kind`;
  - `group`: one of `Naive`, `Advanced`, `Brackets`, `Memory`, `Ours (AAES)`, `Ablations`;
  - `description`: one line a professor understands in five seconds.
- If a preset cannot run in the current context, the API returns the reason (HTTP 422 from
  `check_runnable`) and the UI shows the preset as disabled with that reason. Never fail silently.
  Examples of such contexts:
  - the index has no applicability tags;
  - an oracle method needs a labeled demo case;
  - an Ollama model is missing.
- **Compare mode:** the UI can run one question through 2–4 selected presets and show the results
  side by side, one column per preset: answer, AAES action badge, citations, latency. Clicking a
  column opens that run's Execution trace. Runs are sequential, because the Mac has 16 GB.
- Every AAES step writes its typed input and output into the execution trace, so the Execution tab
  shows the profile, applicability labels, branches, information gain, and the decision.
- Memory methods show the remembered profile in the UI, with a "reset memory" button.
- Demo cases come from the **dev** split only, never from test.

## Coding style: Ponytail, with project overrides

Use the Ponytail skill for all code. These project overrides win over Ponytail:

- Simplify implementation, never remove functionality. Keep every implemented method, registry
  entry, preset, metric, TODO extension point, UI feature, API endpoint, and database safeguard.
- Readability for beginner students beats line count.
- New method = subclass + registry entry + preset (if it is a baseline) + one small test.
- New metric = function + unit test with a hand-computed example in the docstring.
- `shortcut:` comments are allowed for deliberate shortcuts.

## Data rules

- Allowed sources (English only):
  1. `oia.hanyang.ac.kr` — English text blocks and English attachments only (the site is mostly Korean).
  2. `global.hanyang.ac.kr/eng/` — ERICA OIA English site, including its English boards
     (`bo_table=*_eng`).
  3. `studyerica.hanyang.ac.kr/eng/` — only after its robots.txt and content are checked (Gate G2).
  Anything else needs human approval.
- Polite crawling: obey robots.txt, at least 2.5 s between requests, one request at a time,
  identifying User-Agent, raw bytes stored once, never re-crawl a frozen snapshot.
- Mask every e-mail address in extracted text. Never crawl or index staff directories or personal data.
- Do NOT commit: `Sources/data/HYU/raw/`, benchmark files, `Report/course/` (course slides), `.env` files,
  large per-query raw results. Commit code, manifests, labels, small result summaries.
  The GitHub repository is public.

## Evaluation rules (Lesson 6)

- Dev/test separation. Thresholds, prompts, λ/μ, and model choices are tuned on dev only.
- After Gate G4, `Sources/data/HYU/labels/test.jsonl` is frozen; its SHA-256 is in
  `Sources/data/HYU/labels/FROZEN.sha256`. Agents never open it directly afterwards; only the runner reads it.
- A test run requires a clean git tree and `--confirm-frozen`. Each test run is appended to
  `Report/results/TEST_RUNS.md` (date, git SHA, configs, reason).
- Never invent numbers. Every number in `Report/` traces to a file in `Report/results/`.
- Each run manifest versions three things:
  - case version (label file SHA);
  - system version (git SHA + registry config hash);
  - evaluator version (metric code SHA + judge model/prompt hash).

## Labeling rules

- Every label row records `annotator` (`codex:<model>`, `claude-code:<model>`, `human:<initials>`)
  and `origin` (`human`, `agent_draft_human_edited`, `agent_draft`).
- Independent annotation: an annotator never reads another annotator's label file before
  submitting its own.
- Labeling agents never see system outputs or results.
- Final labels are human-adjudicated. Every test item is human-verified.

## Network and long jobs

Agents do not run crawls, dataset downloads, index builds, or full evaluation runs. They write the
code and print the exact command, and a human runs it in a terminal (`conda activate RAG`).
Agents may run unit tests and `--dry-run` / `--smoke` commands.

## Definition of done (every task)

1. Tests pass: `cd Sources/backend && pytest -q` and `cd Sources && pytest -q evaluation/tests`
   (plus the tests of any new package, e.g. `pytest -q crawler/tests labeling/tests`).
2. `cd Sources && python -m evaluation.runner --suite all --dry-run` passes, and the registry
   check passes.
3. If the task adds or changes a method, preset, API field, or UI component:
   - `cd Sources/frontend && npm run typecheck && npm test` pass;
   - the preset appears in `GET /api/pipeline/presets`, either enabled or disabled with a reason;
   - a backend test calls `/api/chat` with that preset on the synthetic fixture index (mock Ollama).
4. Docs touched by the change are updated (`Sources/docs/*`).
5. A result note exists: `Sources/docs/agent_tasks/T<NN>.result.md`. It covers what changed,
   what was skipped or not checked, risks, and the exact commands the human must run.
6. `Report/project/STATUS.md` has one new line.

## Writing rules (Report/)

- Plain technical prose in the team's voice. Numbers only from `Report/results/`.
- Use the professor's terms: eligibility vs relevance, candidate retrieval vs evidence selection,
  prefiltering vs postfiltering, evidence sufficiency, abstention.
- Run the Humanizer skill on every prose file before review, matching `Report/voice_sample.md`.
- Keep `Report/ai_use_statement.md` up to date with which tools did what.
