# Benchmark summary — run `deck5-dev2`

Git `55f9ce543d` (uncommitted changes) · split `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2`, `hyu: dev2` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.16

Task status: COMPLETED: 15

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

## HYU suite — dev2

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 60 | 0.317 | 0.167 | 0.400 | 0.142 | 0.581 | 0.578 | 0.000 | N/A | 0.053 | N/A | 0.474 | 345.100 | 0.317 |
| AP_BBBB | all | 60 | 0.817 | 0.333 | 0.500 | 0.200 | 0.129 | 0.603 | 0.000 | 0.000 | 0.041 | 0.000 | 0.041 | 4556.900 | 3.800 |
| AP_BBBR | all | 60 | 0.817 | 0.333 | 0.500 | 0.200 | 0.129 | 0.603 | 0.000 | 0.000 | 0.041 | 0.000 | 0.041 | 246.500 | 3.617 |
| AP_BBRB | all | 60 | 0.700 | 0.367 | 0.567 | 0.268 | 0.194 | 0.603 | 0.000 | 0.000 | 0.048 | 0.000 | 0.048 | 270.400 | 3.000 |
| AP_BRBB | all | 60 | 0.550 | 0.167 | 0.367 | 0.122 | 0.323 | 0.603 | 0.000 | 0.000 | 0.091 | 0.000 | 0.364 | 5612.700 | 3.667 |
| AP_BRRR | all | 60 | 0.317 | 0.200 | 0.433 | 0.165 | 0.581 | 0.603 | 0.000 | N/A | 0.053 | N/A | 0.474 | 255.100 | 1.317 |
| AP_LLLL | all | 60 | 0.800 | 0.333 | 0.517 | 0.211 | 0.065 | 0.583 | 0.000 | 0.000 | 0.021 | 0.000 | 0.042 | 16581.800 | 4.783 |
| AP_LRRR | all | 60 | 0.333 | 0.200 | 0.433 | 0.163 | 0.581 | 0.603 | 0.000 | N/A | 0.050 | N/A | 0.450 | 201.800 | 1.333 |
| AP_RBBB | all | 60 | 0.783 | 0.333 | 0.483 | 0.202 | 0.161 | 0.578 | 0.000 | 0.000 | 0.043 | 0.000 | 0.021 | 42448.000 | 2.867 |
| AP_RBRR | all | 60 | 0.700 | 0.383 | 0.583 | 0.272 | 0.194 | 0.578 | 0.000 | 0.000 | 0.024 | 0.000 | 0.024 | 212.900 | 1.700 |
| AP_RLRR | all | 60 | 0.683 | 0.333 | 0.533 | 0.245 | 0.129 | 0.578 | 0.000 | 0.000 | 0.049 | 0.000 | 0.024 | 775.800 | 1.717 |
| AP_RRBR | all | 60 | 0.483 | 0.183 | 0.367 | 0.139 | 0.387 | 0.578 | 0.000 | 0.000 | 0.069 | 0.000 | 0.379 | 237.200 | 2.150 |
| AP_RRLR | all | 60 | 0.733 | 0.267 | 0.417 | 0.148 | 0.097 | 0.578 | 0.000 | 0.000 | 0.023 | 0.000 | 0.295 | 10790.500 | 1.600 |
| AP_RRRB | all | 60 | 0.317 | 0.167 | 0.400 | 0.142 | 0.581 | 0.578 | 0.000 | N/A | 0.053 | N/A | 0.474 | 264.700 | 1.000 |
| AP_RRRL | all | 60 | 0.433 | 0.183 | 0.417 | 0.160 | 0.419 | 0.578 | 0.000 | 0.000 | 0.038 | 0.000 | 0.462 | 6358.800 | 1.433 |

Per-slice rows: `hyu_dev2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: NOT_RUN: R15_SELF_QUERY has no results
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results
