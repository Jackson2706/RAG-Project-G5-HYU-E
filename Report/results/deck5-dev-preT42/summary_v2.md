# deck5-dev-preT42: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-20T06:16:29+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — dev (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AP_BBBB | all | 47 | 0.617 | 0.532 | 0.617 | 0.347 | 0.050 | 0.471 | 0.000 | 0.000 | 0.000 | 0.250 | 0.207 | 231.600 | 3.553 |
| AP_BBBR | all | 47 | 0.617 | 0.532 | 0.617 | 0.347 | 0.050 | 0.471 | 0.000 | 0.000 | 0.000 | 0.250 | 0.207 | 277.400 | 3.447 |
| AP_BBRB | all | 47 | 0.574 | 0.511 | 0.596 | 0.344 | 0.100 | 0.471 | 0.000 | 0.000 | 0.000 | 0.250 | 0.185 | 235.500 | 3.000 |
| AP_BRBB | all | 47 | 0.362 | 0.340 | 0.447 | 0.242 | 0.300 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.765 | 239.600 | 3.447 |
| AP_BRRR | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 204.500 | 1.362 |
| AP_RBBB | all | 47 | 0.638 | 0.553 | 0.638 | 0.359 | 0.050 | 0.471 | 0.000 | 0.000 | 0.000 | 0.250 | 0.200 | 225.700 | 2.553 |
| AP_RRBR | all | 47 | 0.362 | 0.340 | 0.447 | 0.242 | 0.300 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.765 | 219.600 | 1.915 |

Per-slice rows: `hyu_dev_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):


