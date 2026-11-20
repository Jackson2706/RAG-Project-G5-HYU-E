# Benchmark summary — run `heldout-test3`

Git `209b169928` (uncommitted changes) · split `hyu: test3`, `hyu: test3` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.16

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

## HYU suite — test3

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 140 | 0.307 | 0.086 | 0.300 | 0.075 | 0.534 | 0.648 | 0.067 | 0.000 | 0.047 | 0.000 | 0.442 | 413.600 | 0.329 |
| AP_BBBB | all | 140 | 0.793 | 0.386 | 0.550 | 0.225 | 0.091 | 0.648 | 0.067 | 0.333 | 0.081 | 0.143 | 0.027 | 41997.700 | 3.879 |
| AP_RRRL | all | 140 | 0.464 | 0.207 | 0.414 | 0.175 | 0.341 | 0.648 | 0.067 | 0.000 | 0.031 | 0.143 | 0.369 | 10215.100 | 1.493 |
| B0_BASIC_DENSE_RAG | all | 140 | 0.879 | 0.379 | 0.543 | 0.144 | 0.000 | 0.548 | 0.067 | 0.333 | 0.073 | 0.143 | 0.000 | 9797.200 | 1.000 |
| G1_ORACLE_CONTEXT | all | 140 | 0.943 | 0.486 | 0.629 | 0.258 | 0.000 | N/A | N/A | 0.000 | 0.045 | 0.000 | 0.000 | 6865.000 | 0.971 |
| R15_SELF_QUERY | all | 140 | 0.907 | 0.421 | 0.564 | 0.186 | 0.000 | 0.523 | 0.067 | 0.333 | 0.055 | 0.000 | 0.000 | 11212.000 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 140 | 0.957 | 0.436 | 0.593 | 0.169 | 0.000 | 0.654 | 0.067 | 0.333 | 0.097 | 0.143 | 0.000 | 11488.100 | 1.000 |

Per-slice rows: `hyu_test3_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: AER: NOT_RUN: 0 of 0 cases with inapplicable spans answered by both
- A0_AAES vs R15_SELF_QUERY: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results
