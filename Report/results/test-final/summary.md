# Benchmark summary — run `test-final`

Git `1c64d7b923` (uncommitted changes) · split `hyu: test`, `hyu: test` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.15

Task status: COMPLETED: 13

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

## HYU suite — test

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 121 | 0.347 | 0.174 | 0.248 | 0.160 | 0.443 | 0.459 | 0.077 | 0.286 | 0.048 | 0.400 | 0.619 | 299.800 | 0.413 |
| A1_AAES_HARD_FILTER | all | 121 | 0.355 | 0.165 | 0.240 | 0.155 | 0.462 | 0.461 | 0.092 | 0.286 | 0.047 | 0.500 | 0.605 | 326.900 | 0.430 |
| A2_AAES_ORACLE_PROFILE | all | 121 | 0.355 | 0.165 | 0.248 | 0.156 | 0.415 | 0.467 | 0.077 | 0.286 | 0.093 | 0.200 | 0.628 | 678.600 | 0.421 |
| A3_AAES_ALWAYS_CLARIFY | all | 121 | 0.083 | 0.182 | 0.248 | 0.148 | 0.708 | 0.459 | 0.077 | 0.000 | 0.100 | 1.000 | 1.000 | 202.300 | 0.132 |
| A4_QUESTION_ONLY_AMBIGUITY | all | 121 | 0.521 | 0.388 | 0.496 | 0.226 | 0.236 | 0.459 | 0.077 | 0.125 | 0.079 | 0.455 | 0.587 | 4323.400 | 0.628 |
| A6_AAES_NO_TEMPORAL | all | 121 | 0.347 | 0.174 | 0.248 | 0.160 | 0.443 | 0.459 | 0.077 | 0.286 | 0.048 | 0.400 | 0.619 | 326.600 | 0.413 |
| B0_BASIC_DENSE_RAG | all | 121 | 0.835 | 0.587 | 0.736 | 0.288 | 0.000 | 0.469 | 0.046 | 0.000 | 0.099 | 0.385 | 0.000 | 8366.000 | 1.000 |
| G0_CLOSED_BOOK | all | 121 | 1.000 | 0.496 | 0.661 | 0.166 | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0.000 | 14732.500 | 1.000 |
| G1_ORACLE_CONTEXT | all | 121 | 0.727 | 0.669 | 0.818 | 0.350 | 0.000 | N/A | N/A | 0.000 | 0.080 | 0.000 | 0.000 | 2893.600 | 0.810 |
| R15_SELF_QUERY | all | 121 | 0.835 | 0.545 | 0.711 | 0.263 | 0.000 | 0.411 | 0.077 | 0.250 | 0.129 | 0.385 | 0.000 | 14398.700 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 121 | 0.860 | 0.545 | 0.694 | 0.255 | 0.000 | 0.428 | 0.062 | 0.167 | 0.154 | 0.429 | 0.000 | 16026.700 | 1.000 |
| R5_HYBRID_CROSS_ENCODER | all | 121 | 0.818 | 0.521 | 0.669 | 0.249 | 0.000 | 0.428 | 0.062 | 0.091 | 0.121 | 0.429 | 0.000 | 9929.200 | 1.000 |
| R9S_SCOPE_PREFILTER | all | 121 | 0.835 | 0.521 | 0.686 | 0.245 | 0.000 | 0.463 | 0.092 | 0.300 | 0.069 | 0.429 | 0.000 | 9245.900 | 1.000 |

Per-slice rows: `hyu_test_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: AER (conditional + temporal, both answered; 2 of 6 cases with inapplicable spans answered by both): diff +0.000 [+0.000, +0.000], p 1.0000, Holm 1.0000 (n=2)
- A0_AAES vs R15_SELF_QUERY: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: diff -0.066 [-0.128, +0.000], p 0.1310, Holm 0.3930 (n=121)
