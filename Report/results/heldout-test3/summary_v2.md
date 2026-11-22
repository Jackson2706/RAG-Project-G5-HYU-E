# heldout-test3: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-20T16:34:09+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — test3 (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 140 | 0.300 | 0.093 | 0.314 | 0.086 | 0.534 | 0.648 | 0.067 | 0.000 | 0.024 | 0.000 | 0.452 | 413.600 | 0.329 |
| AP_BBBB | all | 140 | 0.700 | 0.386 | 0.536 | 0.247 | 0.080 | 0.648 | 0.067 | 0.333 | 0.010 | 0.143 | 0.031 | 41997.700 | 3.879 |
| AP_RRRL | all | 140 | 0.450 | 0.214 | 0.429 | 0.181 | 0.341 | 0.648 | 0.067 | 0.000 | 0.016 | 0.143 | 0.365 | 10215.100 | 1.493 |
| B0_BASIC_DENSE_RAG | all | 140 | 0.679 | 0.357 | 0.493 | 0.188 | 0.000 | 0.548 | 0.067 | 0.500 | 0.000 | 0.167 | 0.000 | 9797.200 | 1.000 |
| G1_ORACLE_CONTEXT | all | 140 | 0.864 | 0.507 | 0.629 | 0.285 | 0.000 | N/A | N/A | 0.000 | 0.008 | 0.000 | 0.000 | 6865.000 | 0.971 |
| R15_SELF_QUERY | all | 140 | 0.721 | 0.393 | 0.536 | 0.222 | 0.000 | 0.523 | 0.067 | 0.333 | 0.010 | 0.000 | 0.000 | 11212.000 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 140 | 0.779 | 0.429 | 0.579 | 0.244 | 0.000 | 0.654 | 0.067 | 0.333 | 0.009 | 0.200 | 0.000 | 11488.100 | 1.000 |

Per-slice rows: `hyu_test3_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: AER: NOT_RUN: 0 of 0 cases with inapplicable spans answered by both
- A0_AAES vs R15_SELF_QUERY: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results

