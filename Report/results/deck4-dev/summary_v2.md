# deck4-dev: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-20T05:31:09+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — dev (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 1256.400 | 0.362 |
| AP_BBBB | all | 47 | 0.426 | 0.447 | 0.511 | 0.359 | 0.225 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.050 | 26758.100 | 4.085 |
| AP_BBBR | all | 47 | 0.426 | 0.447 | 0.511 | 0.359 | 0.225 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.050 | 390.900 | 3.723 |
| AP_BBRB | all | 47 | 0.426 | 0.383 | 0.447 | 0.320 | 0.300 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.050 | 282.300 | 2.745 |
| AP_BRBB | all | 47 | 0.362 | 0.362 | 0.468 | 0.254 | 0.300 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.765 | 279.700 | 3.447 |
| AP_BRRR | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 249.600 | 1.362 |
| AP_LLLL | all | 47 | 0.617 | 0.596 | 0.638 | 0.379 | 0.000 | 0.432 | 0.033 | 0.000 | 0.000 | 0.250 | 0.103 | 80154.100 | 4.702 |
| AP_LRRR | all | 47 | 0.213 | 0.234 | 0.340 | 0.178 | 0.475 | 0.447 | 0.000 | 0.000 | 0.000 | 0.500 | 0.800 | 323.300 | 1.319 |
| AP_RBBB | all | 47 | 0.426 | 0.447 | 0.511 | 0.359 | 0.225 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.050 | 275.400 | 3.085 |
| AP_RBRR | all | 47 | 0.426 | 0.383 | 0.447 | 0.320 | 0.300 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.050 | 247.900 | 1.319 |
| AP_RLRR | all | 47 | 0.574 | 0.532 | 0.617 | 0.320 | 0.100 | 0.432 | 0.033 | 0.000 | 0.000 | 0.250 | 0.074 | 7269.400 | 1.809 |
| AP_RRBR | all | 47 | 0.362 | 0.362 | 0.468 | 0.254 | 0.300 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.765 | 295.700 | 1.915 |
| AP_RRLR | all | 47 | 0.489 | 0.298 | 0.340 | 0.229 | 0.200 | 0.471 | 0.000 | 0.000 | 0.043 | 0.250 | 0.652 | 8095.000 | 1.404 |
| AP_RRRB | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 429.400 | 1.000 |
| AP_RRRL | all | 47 | 0.319 | 0.298 | 0.383 | 0.253 | 0.400 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.800 | 6268.400 | 1.404 |

Per-slice rows: `hyu_dev_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: NOT_RUN: R15_SELF_QUERY has no results
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results

