# T44 — deck v5 analysis: dev ablation table, held-out hypotheses, blind judge items, score-content
Owner: Codex (gpt-6.1-sol) · Reviewer: Claude Code · Phase: deck v5 Phases 2, 3, 5

Goal: one script that turns finished runs into the tables of the v5 brief. It reads saved records only; it never runs
a system and never calls an LLM.

Read first: AGENTS.md; Sources/evaluation/hyu_suite.py (load_cases, trace_record fields incl. llm_calls, total_ms,
aaes_plus); Sources/evaluation/reply_action.py (reply_actions_v2.jsonl schema); Sources/evaluation/stats.py or
wherever paired bootstrap / Holm / McNemar helpers already live (grep; reuse them, do not reimplement);
Sources/scripts/export_judge_items.py (the v3 item fields and the blind-key pattern); Sources/scripts/deck_v4_followup.py
(`merge_judgments`, `JUDGE_KEYS`); Sources/evaluation/judge_v3_prompt.md.
Allowed write paths: Sources/scripts/deck_v5.py (new), Sources/evaluation/tests/test_deck_v5.py (new),
Sources/docs/agent_tasks/T44.result.md. Do not touch anything else. Do not commit or push. Never open
Sources/data/HYU/labels/test*.jsonl yourself; the script reads labels only through hyu_suite.load_cases at run time.

Definitions (per case, v2 reply type = the label in <run>/reply_actions_v2.jsonl for (preset, qid)):
- acceptable = v2 type in case.acceptable_behaviors.
- needed = case.expected_behavior in {conditional_answer, clarify}; kept = needed and v2 type in {conditional_answer, clarify}.
- unneeded = case.expected_behavior in {answer, abstain} and v2 type in {clarify, conditional_answer} and not acceptable.
- wrong_referral = v2 type == abstain and abstain not in case.acceptable_behaviors.
- student_dependent = case["student_dependent"] if the field exists, else expected_behavior in {conditional_answer, clarify}.
- llm_calls, seconds = the record's llm_calls and total_ms/1000.

Subcommands (python scripts/deck_v5.py <cmd> ...):
1. `ablation --runs <run_id>[,<run_id>...] --splits dev,dev2 --timing <timing.csv>` →
   Report/slides/deck_v4/aaes_plus/dev_ablation.csv: one row per preset over all cases of the given splits: cases,
   acceptable_rate, needed, kept, kept_rate, unneeded, wrong_referrals, llm_calls_mean, fresh_seconds_median (from the
   timing csv: preset, seconds per question; blank if absent). Plus `select`: print the AAES+ choice by the fixed rule:
   among AP_* versions with kept >= 0.8 × kept(A0_AAES = RRRR), the highest acceptable_rate; ties → fewer llm_calls_mean;
   write the rule, the numbers and the choice to aaes_plus/selection.json.
2. `heldout --run <run_id> --splits test3,test2 --ours <preset> --aaes A0_AAES --conditional R16_PROMPTED_CONDITIONAL`
   Uses only cases that have a v2 label for EVERY preset of the run (balanced). Writes Report/slides/deck_v4/heldout/
   reply_types.csv (preset × split × slice: cases, acceptable_rate, kept_rate, unneeded_rate, wrong_referral_rate,
   seconds_median) and hypotheses.json:
   H1 ours > aaes on acceptable (all cases) — one-sided paired;
   H2 non-inferiority on student_dependent cases: kept_rate(ours) − kept_rate(aaes) > −0.10 (lower CI bound);
   H3 ours > conditional on acceptable, student_dependent cases.
   Each: difference, paired bootstrap 95% CI (10,000 resamples, seed 0), McNemar exact p (one-sided where the
   hypothesis is), Holm-corrected over H1–H3, decision. Secondary (no correction): unneeded rate, wrong referrals,
   seconds. Record case counts and which cases were dropped as unbalanced.
3. `judge-items --run <run_id> --splits test3,test2 --presets <p1,p2,...> --gold-preset G1_ORACLE_CONTEXT` →
   Report/slides/deck_v4/heldout/judge/items.jsonl (every answered reply — v2 type answer or conditional_answer — of
   the given presets, shuffled with a fixed seed, ids H0001…, exactly the fields judge_v3_prompt.md lists, same
   construction as export_judge_items.py), items_gold.jsonl (G1 separately, ids G0001…), key.jsonl (id → preset,
   split, case_id). items*.jsonl will be gitignored by Claude Code; key.jsonl is committed.
4. `score-content --dir Report/slides/deck_v4/heldout/judge [--gold]` → merges judgments_*.jsonl with the strict
   merge check of deck_v4_followup.merge_judgments (exact id coverage, JUDGE_KEYS, facts aligned to required_facts;
   reuse/generalise it, do not weaken it), then per preset (overall and student_dependent): facts covered
   (correct/required), wrong fact rate, wrong group rate, citation support (supported/cited sentences), each with a
   bootstrap 95% CI over cases; writes content_scores.csv and content.json with prompt/item/judgment SHA-256.

Tests (synthetic runs and labels in tmp_path, monkeypatched label loading): each definition on a hand-made case;
selection rule incl. the 80% gate and the tie rule; balanced-case dropping; H2 decision on a hand-computed CI;
judge-items fields match the v3 prompt and the key round-trips; score-content rejects a missing id, an extra key and
a misaligned facts list.
Verify with: cd Sources && pytest -q evaluation/tests/test_deck_v5.py && pytest -q evaluation/tests
Done when: AGENTS.md Definition of done items 1, 5.
