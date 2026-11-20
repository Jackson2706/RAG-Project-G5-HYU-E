# Benchmark summary — run `deck5-dev`

Git `faf41793d4` · split `hyu: dev` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.16

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

## HYU suite — dev

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_AAES | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 142.900 | 0.362 |
| AP_BBBB | all | 47 | 0.745 | 0.574 | 0.660 | 0.363 | 0.050 | 0.447 | 0.000 | 0.000 | 0.057 | 0.400 | 0.171 | 924.700 | 3.745 |
| AP_BBBR | all | 47 | 0.745 | 0.574 | 0.660 | 0.363 | 0.050 | 0.447 | 0.000 | 0.000 | 0.057 | 0.400 | 0.171 | 274.900 | 3.638 |
| AP_BBRB | all | 47 | 0.702 | 0.511 | 0.574 | 0.342 | 0.100 | 0.447 | 0.000 | 0.000 | 0.061 | 0.400 | 0.152 | 271.700 | 3.000 |
| AP_BRBB | all | 47 | 0.319 | 0.404 | 0.511 | 0.279 | 0.350 | 0.447 | 0.000 | 0.000 | 0.067 | 0.333 | 0.733 | 261.900 | 3.702 |
| AP_BRRR | all | 47 | 0.191 | 0.234 | 0.340 | 0.178 | 0.500 | 0.447 | 0.000 | 0.000 | 0.000 | 0.500 | 0.778 | 205.500 | 1.298 |
| AP_LLLL | all | 47 | 0.723 | 0.468 | 0.574 | 0.328 | 0.025 | 0.432 | 0.033 | 0.167 | 0.088 | 0.400 | 0.118 | 256.200 | 4.723 |
| AP_LRRR | all | 47 | 0.213 | 0.234 | 0.340 | 0.178 | 0.475 | 0.447 | 0.000 | 0.000 | 0.000 | 0.500 | 0.800 | 231.700 | 1.319 |
| AP_RBBB | all | 47 | 0.766 | 0.596 | 0.681 | 0.375 | 0.050 | 0.471 | 0.000 | 0.000 | 0.056 | 0.400 | 0.167 | 231.600 | 2.660 |
| AP_RBRR | all | 47 | 0.723 | 0.553 | 0.638 | 0.362 | 0.100 | 0.471 | 0.000 | 0.000 | 0.059 | 0.400 | 0.147 | 235.800 | 1.872 |
| AP_RLRR | all | 47 | 0.681 | 0.511 | 0.617 | 0.304 | 0.100 | 0.432 | 0.033 | 0.200 | 0.094 | 0.400 | 0.094 | 217.100 | 1.830 |
| AP_RRBR | all | 47 | 0.404 | 0.404 | 0.511 | 0.278 | 0.275 | 0.471 | 0.000 | 0.000 | 0.053 | 0.333 | 0.737 | 257.000 | 2.106 |
| AP_RRLR | all | 47 | 0.489 | 0.319 | 0.383 | 0.258 | 0.200 | 0.471 | 0.000 | 0.000 | 0.043 | 0.250 | 0.652 | 206.700 | 1.404 |
| AP_RRRB | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 198.200 | 1.000 |
| AP_RRRL | all | 47 | 0.319 | 0.298 | 0.383 | 0.253 | 0.400 | 0.471 | 0.000 | 0.000 | 0.000 | 0.333 | 0.800 | 218.200 | 1.404 |

Per-slice rows: `hyu_dev_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: NOT_RUN: R15_SELF_QUERY has no results
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results
