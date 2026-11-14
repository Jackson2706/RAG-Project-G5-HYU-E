# Gates log (A33 autonomous mode)

G1–G3 were passed by the human (see STATUS.md). G4–G7 are checked automatically by Claude Code.
Each entry: date, criteria, evidence (file or command), outcome.

## G4 — labels (criteria)
1. All 47 adjudication-sheet rows decided by a fresh subagent, each citing a GUIDELINES v1.3 rule and quoting evidence; ungrounded → EXCLUDE.
2. `labeling.merge merge` succeeds with 0 pending rows.
3. Deterministic checks (`labeling.checks`) run on all cases; violations listed, none fixed silently.
4. Every test-slice candidate and every violation verified by a fresh subagent on a model different from the case's primary annotator; unresolved → EXCLUDE.
5. `labeling.freeze` (dev 50, seed 13, stratified) writes dev/test and FROZEN.sha256; exclusions in `labels/excluded.jsonl`.
6. Test split ≥ 110 cases, else STOP.

## G5 — config freeze (criteria)
A dev run completes with no errors and every pre-registered comparison present (incl. A4); no parameter changed from the 2026-11-13 defaults; `git tag config-freeze`.

## G6 — test run (criteria)
Exactly one `test-final` run on a clean tree with `--confirm-frozen`, logged in `Report/results/TEST_RUNS.md`. Re-run only after a crash or infra failure, with the reason logged.

## G7 — report (criteria)
`Report/report/draft.md` and `Report/slides/outline.md` exist; every number in them traced to `Report/results/` by a script check; limitations state LLM-annotated labels.

## Log
- 2026-11-13: A33 recorded; G4 started.
- 2026-11-13 **G4 PASS (automatic, A33).**
  1. Adjudication: 47 sheet rows by a fresh `claude-code:claude-opus-5-5` subagent, rule + verbatim quote each (`Report/results/labels/adjudication_v12/decisions_a33.jsonl`); 16 proposals accepted; T14-026 EXCLUDE (the decision needs gold spans the sheet cannot add).
  2. Merge: 180 cases, 0 pending; rows off the sheet accepted by `claude-code:claude-opus-5-5`.
  3. `labeling.checks`: 123 violations on 99 cases (`Sources/data/HYU/labels/violations.jsonl`), all sent to verification.
  4. Verification: 154 cases (every test case + every violating dev case) by fresh `claude-code:claude-opus-5-5` subagents (3 sheets + a 16-row re-check with session history that replaces sheet 3's verdicts for those rows); primary annotators were Codex (01-03) and Sonnet 5.5 (04-06). 0 unverified; 11 EXCLUDE.
  5. Freeze: dev 47, test 121, excluded 12 (`labels/excluded.jsonl`), seed 13, dev size 50 before exclusions. FROZEN.sha256: dev 5557a010…, test a622b05e….
  6. Test 121 ≥ 110.

## G5 — 2026-11-13 — PASS (automatic)
- dev-02 (`Report/results/dev-02/`): all 15 tasks COMPLETED, 0 case errors; comparisons 1 and 3 computed, 2 NOT_COMPUTED (needs a human-validated judge, A33).
- No parameter changed between dev-01 and dev-02 (two reporting bugs fixed in code only).
- `best_baseline: R15_SELF_QUERY` (lowest dev AER among B0/R5/R15/R16). Tag `config-freeze`.

## G6 — 2026-11-14 — PASS (automatic)
- One test run, `test-final` (`Report/results/test-final/`, `Report/results/TEST_RUNS.md`), on a clean tree at eaa8b55 with `--confirm-frozen`.
- Infra failure: G1, A0, A1 failed on Qdrant/MongoDB timeouts while the Mac slept on battery (pmset 22:25-22:32, 2026-11-13). Re-run allowed by A33: `--resume` of the same run id at 1c64d7b (differs from eaa8b55 only in Report/ text), only the failed tasks; second TEST_RUNS.md row. Not re-run because of results.
- Final: 13 presets x 121 cases, 0 errors.

## G7 — 2026-11-14 — PASS (automatic)
- `Report/report/draft.md` (sections 1-9) and `Report/slides/outline.md` exist; Humanizer pass done with `Report/voice_sample.md`.
- `python3 Report/notes/check_report_numbers.py`: 101 values checked, 0 mismatches; comparison statistics and AER counts checked against `hyu_test_comparisons_paired.csv` and `hyu_test_per_case.csv`.
- Limitations (section 8) state that labels are LLM-annotated, adjudicated and verified, with no human verification.
- Open for the team: Lessons 3-4 mapping (slides not on this machine), compare-mode screenshots.

## A35 Step 4: AG dev GO / NO-GO (automatic), 2026-11-14

Run dev-04 (R16 base, A0, AG; 47 dev cases), evaluator v2, `Report/results/dev-04/ag_gate.json` (definitions fixed in
`Sources/scripts/ag_gate.py` before the run). AG fired on 1 case (T14-015) and was wrong there: override precision
0.0 < 0.4. Acceptable: AG 0.617, R16 0.702, A0 0.362; unnecessary questions AG 0.0, R16 0.0, A0 0.425. Fixes 0,
breaks 4. **NO-GO.** Of the 3 breaks where the guard did not fire, T14-208 and T14-214 come from a bug (the
evaluator prepends earlier turns to the question only for presets without profile understanding, so AG's
generator lost the history R16 sees) and T14-152 from run-to-run variation (R16's own replies differ in text on
25/47 dev cases between dev-03 and dev-04, with 1 acceptability flip). The bug does not change the decision (the
precision condition fails on the single fire, not a multi-session case), so no re-run. Steps 5-6 skipped: the
frozen test-2 (75 cases) stays unused, kept for future work.
