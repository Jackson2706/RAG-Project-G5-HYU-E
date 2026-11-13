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
