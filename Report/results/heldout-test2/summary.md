# Benchmark summary — run `heldout-test2`

Git `19709c939c` (uncommitted changes) · split `hyu: test2` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.16

Task status: COMPLETED: 7

All numbers below were computed from the saved per-query results. N/A = not measurable (missing labels, not run, or undefined).

## Controlled fixture (5 synthetic HYU documents; author-written labels — not a benchmark)

| experiment | status | cases | candidate_cutoff | target_hit_rate | ineligible_returned_rate | starved_rate | empty_rate | returned_units_mean |
|---|---|---|---|---|---|---|---|---|
| R0_DENSE | NOT_RUN | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| R9_PREFILTERING | NOT_RUN | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| R10_POSTFILTERING | NOT_RUN | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

_No results._

## Limitations

- BEIR measures document ranking. No answer-quality metric is reported without annotated cases.
- Protocol B maps chunk rankings to documents by first appearance; it is not the BEIR leaderboard setting.
- LLM-based methods (R6, R7, R8, R13, R14) ran on a subset of queries; compare them with B0 on the same subset (paired columns).
- One auxiliary LLM was used for all LLM-based retrieval methods; results may differ with another model.
- No hyperparameter was tuned on the test splits: every value is the preset default declared before running.
- Gate and filter results come from a small author-written fixture, not from independent labels.

## HYU suite — test2

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 75 | 0.347 | 0.173 | 0.293 | 0.177 | 0.458 | 0.492 | 0.075 | 0.333 | 0.000 | 0.000 | 0.615 | 304.600 | 0.400 |
| AP_BBBB | all | 75 | 0.747 | 0.573 | 0.613 | 0.379 | 0.085 | 0.492 | 0.075 | 0.000 | 0.018 | 0.400 | 0.054 | 27556.400 | 3.653 |
| AP_RRRL | all | 75 | 0.480 | 0.213 | 0.320 | 0.202 | 0.322 | 0.492 | 0.075 | 0.250 | 0.000 | 0.167 | 0.722 | 6235.700 | 1.533 |
| B0_BASIC_DENSE_RAG | all | 75 | 0.827 | 0.587 | 0.640 | 0.296 | 0.000 | 0.453 | 0.025 | 0.000 | 0.048 | 0.462 | 0.000 | 6396.500 | 1.000 |
| G1_ORACLE_CONTEXT | all | 75 | 0.720 | 0.760 | 0.800 | 0.425 | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0.000 | 3983.300 | 0.800 |
| R15_SELF_QUERY | all | 75 | 0.800 | 0.600 | 0.640 | 0.307 | 0.000 | 0.425 | 0.025 | 0.000 | 0.050 | 0.231 | 0.000 | 7887.600 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 75 | 0.853 | 0.613 | 0.653 | 0.310 | 0.000 | 0.494 | 0.075 | 0.000 | 0.078 | 0.308 | 0.000 | 7868.900 | 1.000 |

Per-slice rows: `hyu_test2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: AER: NOT_RUN: 0 of 2 cases with inapplicable spans answered by both
- A0_AAES vs R15_SELF_QUERY: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results
