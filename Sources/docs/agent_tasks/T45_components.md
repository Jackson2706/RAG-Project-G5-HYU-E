# T45 — deck v5: component numbers from Stage B traces (no new labels)
Owner: Codex (gpt-6.1-sol) · Reviewer: Claude Code · Phase: deck v5 Phase 2 step 4

Read first: AGENTS.md; Sources/scripts/deck_v5.py (reuse load_runs, case_score, BRANCHING, write_csv/json, the
complete-coverage check of T44b); Sources/evaluation/hyu_suite.py (trace_record: `aaes_plus` holds the step outputs,
e.g. branch_attributes, clarify_attribute, reason, profile); an example record in
Report/results/deck4-dev/raw/hyu/dev/AP_BBBB__-.jsonl (dev data; you may read it).
Allowed write paths: Sources/scripts/deck_v5.py, Sources/evaluation/tests/test_deck_v5.py, Sources/docs/agent_tasks/T45.result.md.
Do not commit or push; touch nothing else; never open test labels.

New subcommand `components --runs <run_id,...> --splits dev,dev2` → Report/slides/deck_v4/aaes_plus/components_v5.csv
and components_v5.json, one row per preset (A0_AAES and every AP_*), over all cases of the splits:
- Step 3 detail hit: among cases where the record names a chosen detail (clarify_attribute, or the first of
  branch_attributes for a split) AND the label has non-empty branch_attributes: share whose chosen detail is in the
  label's branch_attributes (with counts).
- Step 3 "needs a split": predicted = the record's AAES decision found a split or asked (aaes_plus branch_attributes
  non-empty, or the record action in CLARIFY/CONDITIONAL); gold = label expected_behavior in {conditional_answer,
  clarify}. Precision, recall, F1 with TP/FP/FN counts.
- Step 4: reply-type confusion of the v2 reply type (reply_actions_v2.jsonl, as in ablation) against
  expected_behavior (4×4 counts) and accuracy.
Document each definition in the docstring; tests with hand-made records.
Verify with: cd Sources && pytest -q evaluation/tests/test_deck_v5.py && pytest -q evaluation/tests
