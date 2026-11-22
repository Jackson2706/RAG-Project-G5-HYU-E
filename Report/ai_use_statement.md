# AI use statement

This project was built with AI coding agents. This file lists which tool did what. It is kept up to date
(AGENTS.md "Writing rules").

## Code

- **Codex CLI** (`codex:gpt-5`) implemented most backend, crawler, evaluation and frontend code from task files
  written by Claude Code (`Sources/docs/agent_tasks/T*.md`, each with a `.result.md`). Earlier Codex changes were
  reviewed and committed by Claude Code. On 2026-11-16 Codex also reconstructed and tested the AAES+ fallback patch
  described in T39, audited the local continuation state, and ran the dev-only model-call probe.
- **Claude Code** (Claude Opus 5.5) planned the phases, wrote specs and tests first for the research-critical
  code (AAES steps and policy, metrics, the split/freeze logic, the test-run guard), reviewed every Codex change,
  and committed. From 2026-11-13 (amendment A33; Codex unavailable until 2026-11-17) Claude Code also wrote code
  directly: the G4 label pipeline, the oracle methods (A2, G1), the demo-case picker, the dev-01 bug fixes and
  `make_report_assets.py`.
- Code reviews of research-critical changes were done by fresh Claude subagents (Opus 5.5 or Sonnet 5.5) that
  had not written the code.

## Questions and labels (all LLM; nothing human-verified)

For the deck-v4 dev2/test3 extension, Codex writers produced 328 candidates from pre-screened official passage
bundles. `codex:gpt-6.1-sol` and `codex:gpt-6-astra` labeled the three blind pools independently. Fresh
`codex:gpt-6.1-terra` contexts adjudicated 57 decision disputes. At the user's request, one verifier model was used:
a fresh `codex:gpt-6-astra` context reviewed every selected test3 case, all 30 flagged dev2 cases and 12 reserve
replacements. It fixed 170 rows across the main and replacement passes and excluded 12 unresolved rows. No person
checked the labels. The final freeze contains 60 dev2 and 140 test3 cases; 87/200 are evidence-supported dependent
cases, below the planned 140/60 balance. Full provenance is in `Report/slides/deck_v4/questions/METHODOLOGY.md`.

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

- Claude Code wrote the optional A0b preset ("AAES spec-fixed") and ran it on dev only (dev-03); a fresh
  `claude-code:claude-sonnet-5-5` subagent reviewed evaluator v2 and A0b, and its one A0b bug was fixed before A0b ran.

## Amendment A35 (2026-11-14)

- Claude Code (Opus 5.5) wrote the case cards (`Report/slides/case_examples.md`, from saved replies only), the AG
  preset and its tests, the dev gate script and the test-2 merge, analysis and guard code.
- Test-2 labels, all by fresh subagents: questions drafted by `claude-code:claude-sonnet-5-5` (titles, personas
  and guidelines only); selection by `claude-code:claude-sonnet-5-5`; blind annotation by
  `claude-code:claude-opus-5-5` (A) and `claude-code:claude-sonnet-5-5` (B); adjudication by
  `claude-code:claude-opus-5-5` (rows built from B) and `claude-code:claude-haiku-5-5` (rows built from A);
  verification of flagged cases by `claude-code:claude-sonnet-5-5` and `claude-code:claude-opus-5-5`, never the
  case's primary annotator's model.

## Evaluator v3 (amendment A36, 2026-11-14)

- Claude Code wrote the judge prompt (`Sources/evaluation/judge_v3_prompt.md`), the item export and the aggregation
  (`Sources/scripts/export_judge_items.py`, `quality_v3.py`).
- Fresh `claude-code:claude-opus-5-5` subagents judged all 1,008 saved replies (6 presets; dev and test-1), blind to
  preset names; a fresh `claude-code:claude-sonnet-5-5` subagent re-judged 100 dev replies for agreement. The judges
  saw the labels and the replies; nothing was re-run.
- A third check came from another vendor: the human ran ChatGPT (GPT-6.1, max thinking) on 20 of the same dev
  replies and saved its judgments in `Report/notes/quality_gpt_check.csv`. No person judged the replies.

## Runs

Claude Code ran the dev runs and the single test run itself (A33), in the background under `caffeinate`, with
logs in `.run/`. The generator inside the system is `qwen3.5:4b` (and `llama2:7b` for the backbone comparison)
through Ollama, running locally.

## Writing

- Report and slide prose was drafted by Claude Code from the result files, then passed through the Humanizer
  skill with `Report/voice_sample.md` as the voice sample. Every number was re-checked against `Report/results/`
  afterwards.
- The demo script and the choice of demo cases (dev split only) were made by Claude Code from dev results.

## Deck v4–v6 (2026-11-16 to 2026-11-21)

- **Claude Code (Claude Opus 5.5)** orchestrated the work: it wrote the task briefs for Codex, reviewed and tested
  every Codex change before committing, ran every dev and held-out run (under `caffeinate`, logs in `.run/`), wrote
  the analysis scripts, the follow-up fix of deck v6 (`Sources/backend/app/rag/followup.py`) and its tests, the demo
  and preflight scripts, and the README, report and slide-facing summaries. It alone committed and pushed.
- **Held-out content judging:** fresh Claude Opus 5.5 subagents (12 batches of answered replies, 5 batches of
  gold-evidence replies) judged blind with the frozen v3 prompt; each saw only the prompt and its batch, and the
  key was read only by the scoring script after all batches were merged.
- **Codex CLI with GPT-6 Sol** (`codex exec -s workspace-write -m gpt-6.1-sol`): code tasks T41–T45 (trace expiry and
  delete, the two AAES+ "both" fixes, the question-major runner, the deck v5 analysis script) under task files in
  `Sources/docs/agent_tasks/`, told not to commit or push and to touch only the files named; code reviews
  (`codex review`); and the blind Task 2 follow-up judging (6 batches, frozen v3 prompt) and the deck v6 dev
  follow-up judging.
- **Labels of dev-2 and test-3:** GPT-6 Sol and GPT-6 Astra (independent annotation),
  GPT-6 Terra (adjudication of disputes) and GPT-6 Astra (single verifier), as described under "Questions and
  labels" above and in `Report/slides/deck_v4/questions/METHODOLOGY.md`. **No person checked the dev-2 or test-3
  labels.**
- The system under test still uses only `qwen3.5:4b` through local Ollama, for generation and for the AAES+ LLM steps.
