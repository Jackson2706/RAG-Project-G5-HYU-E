# deck5-dev2: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-20T08:24:59+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — dev2 (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 60 | 0.317 | 0.133 | 0.383 | 0.117 | 0.581 | 0.578 | 0.000 | N/A | 0.053 | N/A | 0.474 | 345.100 | 0.317 |
| AP_BBBB | all | 60 | 0.700 | 0.317 | 0.483 | 0.239 | 0.065 | 0.603 | 0.000 | 0.000 | 0.000 | 0.000 | 0.048 | 4556.900 | 3.800 |
| AP_BBBR | all | 60 | 0.683 | 0.300 | 0.467 | 0.209 | 0.129 | 0.603 | 0.000 | 0.000 | 0.000 | 0.000 | 0.049 | 246.500 | 3.617 |
| AP_BBRB | all | 60 | 0.583 | 0.350 | 0.550 | 0.306 | 0.129 | 0.603 | 0.000 | 0.000 | 0.000 | 0.000 | 0.057 | 270.400 | 3.000 |
| AP_BRBB | all | 60 | 0.500 | 0.167 | 0.383 | 0.136 | 0.258 | 0.603 | 0.000 | 0.000 | 0.033 | 0.000 | 0.400 | 5612.700 | 3.667 |
| AP_BRRR | all | 60 | 0.317 | 0.150 | 0.400 | 0.128 | 0.581 | 0.603 | 0.000 | N/A | 0.053 | N/A | 0.474 | 255.100 | 1.317 |
| AP_LLLL | all | 60 | 0.733 | 0.350 | 0.500 | 0.244 | 0.065 | 0.583 | 0.000 | 0.000 | 0.000 | 0.000 | 0.045 | 16581.800 | 4.783 |
| AP_LRRR | all | 60 | 0.333 | 0.167 | 0.400 | 0.145 | 0.581 | 0.603 | 0.000 | N/A | 0.050 | N/A | 0.450 | 201.800 | 1.333 |
| AP_RBBB | all | 60 | 0.683 | 0.300 | 0.450 | 0.221 | 0.097 | 0.578 | 0.000 | 0.000 | 0.000 | 0.000 | 0.024 | 42448.000 | 2.867 |
| AP_RBRR | all | 60 | 0.600 | 0.333 | 0.533 | 0.260 | 0.194 | 0.578 | 0.000 | 0.000 | 0.000 | 0.000 | 0.028 | 212.900 | 1.700 |
| AP_RLRR | all | 60 | 0.600 | 0.333 | 0.517 | 0.271 | 0.129 | 0.578 | 0.000 | 0.000 | 0.000 | 0.000 | 0.028 | 775.800 | 1.717 |
| AP_RRBR | all | 60 | 0.450 | 0.167 | 0.367 | 0.123 | 0.387 | 0.578 | 0.000 | 0.000 | 0.037 | 0.000 | 0.407 | 237.200 | 2.150 |
| AP_RRLR | all | 60 | 0.700 | 0.233 | 0.417 | 0.138 | 0.097 | 0.578 | 0.000 | 0.000 | 0.000 | 0.000 | 0.286 | 10790.500 | 1.600 |
| AP_RRRB | all | 60 | 0.350 | 0.150 | 0.400 | 0.143 | 0.484 | 0.578 | 0.000 | 0.000 | 0.048 | N/A | 0.429 | 264.700 | 1.000 |
| AP_RRRL | all | 60 | 0.433 | 0.150 | 0.400 | 0.131 | 0.419 | 0.578 | 0.000 | 0.000 | 0.038 | 0.000 | 0.462 | 6358.800 | 1.433 |

Per-slice rows: `hyu_dev2_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: NOT_RUN: R15_SELF_QUERY has no results
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results

