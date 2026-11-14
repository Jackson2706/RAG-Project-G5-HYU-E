# AI use statement

This project was built with AI coding agents. This file lists which tool did what. It is kept up to date
(AGENTS.md "Writing rules").

## Code

- **Codex CLI** (`codex:gpt-5`) implemented most backend, crawler, evaluation and frontend code from task files
  written by Claude Code (`Sources/docs/agent_tasks/T*.md`, each with a `.result.md`). Codex never committed.
- **Claude Code** (Claude Opus 5.5) planned the phases, wrote specs and tests first for the research-critical
  code (AAES steps and policy, metrics, the split/freeze logic, the test-run guard), reviewed every Codex change,
  and committed. From 2026-11-13 (amendment A33; Codex unavailable until 2026-11-17) Claude Code also wrote code
  directly: the G4 label pipeline, the oracle methods (A2, G1), the demo-case picker, the dev-01 bug fixes and
  `make_report_assets.py`.
- Code reviews of research-critical changes were done by fresh Claude subagents (Opus 5.5 or Sonnet 5.5) that
  had not written the code.

## Questions and labels (all LLM; nothing human-verified)

| Step | Who | Cases |
|---|---|---|
| Questions | Codex and Claude Code (agent-written; no human-written question, PLAYBOOK A28) | 180 |
| Primary annotation, batches 01-03 | `codex:gpt-5` | |
| Primary annotation, batches 04-06 | `claude-code:claude-sonnet-5-5` | |
| Adjudication of disputed/flagged rows | fresh `claude-code:claude-opus-5-5` subagent | 47 rows |
| Deterministic checks | `labeling.checks` (no model) | 123 violations on 99 cases |
| Verification of every test case and every flagged case | fresh `claude-code:claude-opus-5-5` subagents, never the case's primary annotator | 154 |

Labelling agents never saw system outputs. Annotators did not read each other's files. The frozen split has
47 dev and 121 test cases; 12 were excluded (`Sources/data/HYU/labels/excluded.jsonl`). The test set is
LLM-annotated, so every result is a relative comparison between methods on these labels
(`Report/project/gates.md`, G4).

## Evaluator v2 (amendment A34, 2026-11-14)

- Claude Code (Opus 5.5) wrote evaluator v2 (`Sources/evaluation/reply_action.py`, `evaluation/rescore.py`), the
  post-hoc analysis script and the A0 dev decision diagnostics, from findings that came out of a review in the
  planning chat (Claude).
- v2 labels each saved reply with fixed rules or, for the rest, `qwen3.5:4b` (temperature 0, seed 42, prompt hash
  in `summary_v2.md`). The rules and prompt were written on dev outputs only and committed before any test output
  was classified.
- A fresh `claude-code:claude-opus-5-5` subagent labelled a stratified sample of 100 dev replies. It saw only the
  reply text, with no preset names and no v2 labels. Agreement with v2: kappa 0.899
  (`Report/results/dev-02/v2_validation_summary.json`).
- This step necessarily shows system outputs to a labelling agent. It labels reply form, not the cases, and the case
  labels were not changed.

## Runs

Claude Code ran the dev runs and the single test run itself (A33), in the background under `caffeinate`, with
logs in `.run/`. The generator inside the system is `qwen3.5:4b` (and `llama2:7b` for the backbone comparison)
through Ollama, running locally.

## Writing

- Report and slide prose was drafted by Claude Code from the result files, then passed through the Humanizer
  skill with `Report/voice_sample.md` as the voice sample. Every number was re-checked against `Report/results/`
  afterwards.
- The demo script and the choice of demo cases (dev split only) were made by Claude Code from dev results.
