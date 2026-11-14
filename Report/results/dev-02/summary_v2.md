# dev-02: re-scored with evaluator v2

Evaluator v2 = `evaluation/reply_action.py` (rules + qwen3.5:4b, temperature 0, seed 42, prompt hash `5151f273055b`), 2026-11-14T02:17:22+00:00. Same saved replies as the v1 tables (`summary.md`); no system re-run.
## HYU suite — dev (evaluator v2)

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 648.900 | 0.362 |
| A1_AAES_HARD_FILTER | all | 47 | 0.298 | 0.234 | 0.340 | 0.190 | 0.425 | 0.457 | 0.167 | 0.500 | 0.000 | 0.500 | 0.714 | 507.000 | 0.383 |
| A2_AAES_ORACLE_PROFILE | all | 47 | 0.383 | 0.234 | 0.362 | 0.210 | 0.400 | 0.457 | 0.033 | 0.000 | 0.000 | 0.500 | 0.667 | 586.400 | 0.447 |
| A3_AAES_ALWAYS_CLARIFY | all | 47 | 0.106 | 0.234 | 0.319 | 0.195 | 0.675 | 0.471 | 0.000 | N/A | 0.000 | 1.000 | 1.000 | 228.200 | 0.128 |
| A4_QUESTION_ONLY_AMBIGUITY | all | 47 | 0.404 | 0.489 | 0.532 | 0.307 | 0.300 | 0.471 | 0.000 | 0.000 | 0.000 | 0.250 | 0.789 | 3268.900 | 0.553 |
| A6_AAES_NO_TEMPORAL | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 381.800 | 0.362 |
| B0_BASIC_DENSE_RAG | all | 47 | 0.574 | 0.596 | 0.660 | 0.323 | 0.000 | 0.409 | 0.067 | 0.250 | 0.000 | 0.600 | 0.000 | 7693.100 | 1.000 |
| G0_CLOSED_BOOK | all | 47 | 0.872 | 0.511 | 0.596 | 0.241 | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0.000 | 7270.400 | 1.000 |
| G1_ORACLE_CONTEXT | all | 47 | 0.532 | 0.723 | 0.745 | 0.391 | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0.000 | 3138.600 | 0.745 |
| R15_SELF_QUERY | all | 47 | 0.553 | 0.660 | 0.681 | 0.356 | 0.000 | 0.366 | 0.033 | 0.000 | 0.038 | 0.500 | 0.000 | 10039.900 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 47 | 0.574 | 0.660 | 0.681 | 0.374 | 0.000 | 0.418 | 0.067 | 0.333 | 0.000 | 0.600 | 0.000 | 7517.000 | 1.000 |
| R5_HYBRID_CROSS_ENCODER | all | 47 | 0.574 | 0.702 | 0.723 | 0.380 | 0.000 | 0.418 | 0.067 | 0.333 | 0.037 | 0.400 | 0.000 | 7412.900 | 1.000 |
| R9S_SCOPE_PREFILTER | all | 47 | 0.681 | 0.681 | 0.723 | 0.365 | 0.000 | 0.464 | 0.067 | 0.200 | 0.000 | 0.400 | 0.000 | 4019.200 | 1.000 |

Per-slice rows: `hyu_dev_v2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R5_HYBRID_CROSS_ENCODER: AER (conditional + temporal, both answered; 1 of 4 cases with inapplicable spans answered by both): diff +0.000 [+0.000, +0.000], p 1.0000, Holm 1.0000 (n=1)
- A0_AAES vs R5_HYBRID_CROSS_ENCODER: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: diff -0.105 [-0.185, -0.032], p 0.0108, Holm 0.0324 (n=47)

