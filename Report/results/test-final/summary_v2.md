# test-final: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-14T02:33:55+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — test (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 121 | 0.331 | 0.190 | 0.256 | 0.173 | 0.443 | 0.459 | 0.077 | 0.286 | 0.025 | 0.400 | 0.600 | 299.800 | 0.413 |
| A1_AAES_HARD_FILTER | all | 121 | 0.339 | 0.190 | 0.256 | 0.175 | 0.462 | 0.461 | 0.092 | 0.286 | 0.024 | 0.500 | 0.585 | 326.900 | 0.430 |
| A2_AAES_ORACLE_PROFILE | all | 121 | 0.322 | 0.207 | 0.273 | 0.190 | 0.415 | 0.467 | 0.077 | 0.333 | 0.026 | 0.333 | 0.615 | 678.600 | 0.421 |
| A3_AAES_ALWAYS_CLARIFY | all | 121 | 0.066 | 0.182 | 0.240 | 0.147 | 0.708 | 0.459 | 0.077 | 0.000 | 0.000 | 1.000 | 1.000 | 202.300 | 0.132 |
| A4_QUESTION_ONLY_AMBIGUITY | all | 121 | 0.388 | 0.397 | 0.471 | 0.239 | 0.236 | 0.459 | 0.077 | 0.200 | 0.021 | 0.429 | 0.574 | 4323.400 | 0.628 |
| A6_AAES_NO_TEMPORAL | all | 121 | 0.331 | 0.198 | 0.264 | 0.180 | 0.443 | 0.459 | 0.077 | 0.286 | 0.025 | 0.400 | 0.600 | 326.600 | 0.413 |
| B0_BASIC_DENSE_RAG | all | 121 | 0.562 | 0.545 | 0.661 | 0.292 | 0.000 | 0.469 | 0.046 | 0.000 | 0.000 | 0.375 | 0.000 | 8366.000 | 1.000 |
| G0_CLOSED_BOOK | all | 121 | 0.744 | 0.512 | 0.669 | 0.301 | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0.000 | 14732.500 | 1.000 |
| G1_ORACLE_CONTEXT | all | 121 | 0.545 | 0.628 | 0.719 | 0.334 | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0.000 | 2893.600 | 0.810 |
| R15_SELF_QUERY | all | 121 | 0.554 | 0.545 | 0.661 | 0.291 | 0.000 | 0.411 | 0.077 | 0.286 | 0.000 | 0.222 | 0.000 | 14398.700 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 121 | 0.628 | 0.521 | 0.628 | 0.331 | 0.000 | 0.428 | 0.062 | 0.000 | 0.013 | 0.300 | 0.000 | 16026.700 | 1.000 |
| R5_HYBRID_CROSS_ENCODER | all | 121 | 0.570 | 0.529 | 0.653 | 0.281 | 0.000 | 0.428 | 0.062 | 0.000 | 0.029 | 0.333 | 0.000 | 9929.200 | 1.000 |
| R9S_SCOPE_PREFILTER | all | 121 | 0.587 | 0.521 | 0.653 | 0.277 | 0.000 | 0.463 | 0.092 | 0.333 | 0.000 | 0.333 | 0.000 | 9245.900 | 1.000 |

Per-slice rows: `hyu_test_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: AER (conditional + temporal, both answered; 2 of 6 cases with inapplicable spans answered by both): diff +0.000 [+0.000, +0.000], p 1.0000, Holm 1.0000 (n=2)
- A0_AAES vs R15_SELF_QUERY: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: diff -0.066 [-0.132, +0.005], p 0.1544, Holm 0.4632 (n=121)

