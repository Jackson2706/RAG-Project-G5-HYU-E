# Benchmark summary — run `deck5-dev-preT42`

Git `1441216136` · split `hyu: dev` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.16

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

## HYU suite — dev

| preset | slice | cases | answered_rate | action_accuracy | acceptable_rate | macro_f1 | unnecessary_clarification_rate | applicable_recall@5 | intrusion@5 | aer | uncited_answer_rate | outdated | unknown_caveat_rate | p50_ms | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AP_BBBB | all | 47 | 0.745 | 0.553 | 0.638 | 0.353 | 0.050 | 0.471 | 0.000 | 0.000 | 0.057 | 0.400 | 0.171 | 231.600 | 3.553 |
| AP_BBBR | all | 47 | 0.745 | 0.553 | 0.638 | 0.353 | 0.050 | 0.471 | 0.000 | 0.000 | 0.057 | 0.400 | 0.171 | 277.400 | 3.447 |
| AP_BBRB | all | 47 | 0.702 | 0.532 | 0.617 | 0.350 | 0.100 | 0.471 | 0.000 | 0.000 | 0.061 | 0.400 | 0.152 | 235.500 | 3.000 |
| AP_BRBB | all | 47 | 0.383 | 0.362 | 0.468 | 0.257 | 0.300 | 0.471 | 0.000 | 0.000 | 0.056 | 0.333 | 0.722 | 239.600 | 3.447 |
| AP_BRRR | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 204.500 | 1.362 |
| AP_RBBB | all | 47 | 0.766 | 0.574 | 0.660 | 0.365 | 0.050 | 0.471 | 0.000 | 0.000 | 0.056 | 0.400 | 0.167 | 225.700 | 2.553 |
| AP_RRBR | all | 47 | 0.383 | 0.362 | 0.468 | 0.257 | 0.300 | 0.471 | 0.000 | 0.000 | 0.056 | 0.333 | 0.722 | 219.600 | 1.915 |

Per-slice rows: `hyu_dev_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

