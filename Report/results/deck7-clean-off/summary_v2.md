# deck7-clean-off: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-21T04:21:19+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — dev (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AP_RRRL | all | 47 | 0.319 | 0.298 | 0.383 | 0.253 | 0.400 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.800 | 198.400 | 1.404 |

Per-slice rows: `hyu_dev_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):


