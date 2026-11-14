# Test runs

One row per run on the frozen test split (AGENTS.md).

| Date | Run id | Git SHA | Configs | Reason |
|---|---|---|---|---|
| 2026-11-13 | test-final | eaa8b5586006807a71d85a6b7b1917708792637c | B0_BASIC_DENSE_RAG, R5_HYBRID_CROSS_ENCODER, R9S_SCOPE_PREFILTER, R15_SELF_QUERY, R16_PROMPTED_CONDITIONAL, G0_CLOSED_BOOK, G1_ORACLE_CONTEXT, A0_AAES, A1_AAES_HARD_FILTER, A2_AAES_ORACLE_PROFILE, A3_AAES_ALWAYS_CLARIFY, A4_QUESTION_ONLY_AMBIGUITY, A6_AAES_NO_TEMPORAL | G6: single test run after config-freeze (A33) |
| 2026-11-14 | test-final | 1c64d7b923a500c10cdc5bdb25d5f76155a80c8b | B0_BASIC_DENSE_RAG, R5_HYBRID_CROSS_ENCODER, R9S_SCOPE_PREFILTER, R15_SELF_QUERY, R16_PROMPTED_CONDITIONAL, G0_CLOSED_BOOK, G1_ORACLE_CONTEXT, A0_AAES, A1_AAES_HARD_FILTER, A2_AAES_ORACLE_PROFILE, A3_AAES_ALWAYS_CLARIFY, A4_QUESTION_ONLY_AMBIGUITY, A6_AAES_NO_TEMPORAL | Infra re-run (A33): G1, A0, A1 failed on Qdrant/MongoDB timeouts while the Mac slept on battery (pmset 22:25-22:32, 2026-11-13); --resume runs only the failed tasks (resume) |

Re-scores (no system run; saved replies only, amendment A34):

| Date | Run id | Git SHA | Evaluator | Reason |
|---|---|---|---|---|
| 2026-11-14 | test-final | facacc3 | v2 (`evaluation/reply_action.py`, prompt hash 5151f273055b) | Evaluator v1 cannot score a baseline as conditional_answer or clarify; v2 frozen on dev-02 outputs before this re-score |
