# T44b — Review fixes: complete coverage before selection, planned presets in the balance check
Owner: Codex (gpt-6.1-sol) · Reviewer: Claude Code · Follows T44 (read T44_deck_v5_analysis.md and T44.result.md first)

Must-fix review findings [P2] in Sources/scripts/deck_v5.py:
1. `ablation`/`select`: refuse to write a selection unless A0_AAES and every AP_* candidate have a completed record
   AND a v2 label for exactly the same set of cases (all cases of the requested splits). Raise with the list of
   presets and missing case ids.
2. `heldout` (and `judge-items`): the expected presets come from the run's metadata (run_manifest.json tasks /
   status.json keys for the requested splits), not from the raw files found. A planned preset with no raw file, or
   with any case missing, makes those cases unbalanced (listed in dropped_unbalanced); a planned preset with no
   records at all is an error naming it.

Allowed write paths: Sources/scripts/deck_v5.py, Sources/evaluation/tests/test_deck_v5.py, Sources/docs/agent_tasks/T44b.result.md.
Do not commit or push; touch nothing else.
Tests: an AP run with one case is rejected for selection; a planned preset without a raw file is reported/rejected;
existing tests still pass.
Verify with: cd Sources && pytest -q evaluation/tests/test_deck_v5.py && pytest -q evaluation/tests
