# Benchmark summary — run `deck5-timing`

Git `c989d8ea78` · split `hyu: dev2`, `hyu: dev2` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.16

Task status: COMPLETED: 6, STOPPED: 1

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
| A0_AAES | all | 11 | 0.182 | 0.182 | 0.455 | 0.127 | 0.750 | 0.591 | N/A | N/A | 0.000 | N/A | 0.000 | 316.800 | 0.182 |
| AP_BBBB | all | 11 | 0.818 | 0.091 | 0.455 | 0.050 | 0.000 | 0.591 | N/A | N/A | 0.000 | 0.000 | 0.000 | 33738.300 | 3.909 |
| AP_RRRL | all | 11 | 0.364 | 0.273 | 0.545 | 0.301 | 0.250 | 0.591 | N/A | N/A | 0.000 | 0.000 | 0.000 | 7001.100 | 1.364 |
| B0_BASIC_DENSE_RAG | all | 11 | 0.818 | 0.091 | 0.273 | 0.045 | 0.000 | 0.318 | N/A | N/A | 0.111 | 0.000 | 0.000 | 6202.100 | 1.000 |
| G1_ORACLE_CONTEXT | all | 10 | 0.900 | 0.300 | 0.400 | 0.258 | 0.000 | N/A | N/A | N/A | 0.222 | 0.000 | 0.000 | 13494.100 | 1.000 |
| R15_SELF_QUERY | all | 11 | 1.000 | 0.182 | 0.364 | 0.077 | 0.000 | 0.227 | N/A | N/A | 0.091 | 0.000 | 0.000 | 9693.200 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 11 | 1.000 | 0.182 | 0.364 | 0.077 | 0.000 | 0.682 | N/A | N/A | 0.091 | 0.000 | 0.000 | 12363.100 | 1.000 |

Per-slice rows: `hyu_dev2_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: AER: NOT_RUN: 0 of 0 cases with inapplicable spans answered by both
- A0_AAES vs R15_SELF_QUERY: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: NOT_RUN: A4_QUESTION_ONLY_AMBIGUITY has no results
