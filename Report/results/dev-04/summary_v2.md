# dev-04: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-14T07:01:57+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — dev (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 753.700 | 0.362 |
| AG_AAES_GUARD | all | 47 | 0.596 | 0.596 | 0.617 | 0.347 | 0.000 | 0.432 | 0.033 | 0.000 | 0.000 | 0.600 | 0.036 | 18070.100 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 47 | 0.574 | 0.681 | 0.702 | 0.381 | 0.000 | 0.418 | 0.067 | 0.333 | 0.000 | 0.600 | 0.000 | 9155.600 | 1.000 |

Per-slice rows: `hyu_dev_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: NOT_RUN: R15_SELF_QUERY has no results
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results

