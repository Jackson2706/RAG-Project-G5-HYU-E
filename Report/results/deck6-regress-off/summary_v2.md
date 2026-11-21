# deck6-regress-off: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-21T02:40:43+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — dev (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 160.200 | 0.362 |
| AP_RRRL | all | 47 | 0.319 | 0.298 | 0.383 | 0.253 | 0.400 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.800 | 183.900 | 1.404 |

Per-slice rows: `hyu_dev_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: NOT_RUN: R15_SELF_QUERY has no results
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results

