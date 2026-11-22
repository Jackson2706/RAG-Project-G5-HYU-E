# Benchmark summary — run `dev-02`

Git `3be2dac740` (uncommitted changes) · split `hyu: dev`, `generation: test` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.15

Task status: COMPLETED: 15

All numbers below were computed from the saved per-query results. N/A = not measurable (missing labels, not run, or undefined).

## Controlled fixture (5 synthetic HYU documents; author-written labels — not a benchmark)

| experiment | status | cases | candidate_cutoff | target_hit_rate | ineligible_returned_rate | starved_rate | empty_rate | returned_units_mean |
|---|---|---|---|---|---|---|---|---|
| R0_DENSE | NOT_RUN | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| R9_PREFILTERING | NOT_RUN | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| R10_POSTFILTERING | NOT_RUN | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

_No results._

## Report C — Generation (same cached evidence for both backbones)

| experiment | model | quantization | status | cases | failed | answered_rate | abstention_rate | marker_validity_mean | answers_citing_a_source_rate | invalid_markers_total | generation_ms_p50 | generation_ms_p95 | output_tokens_mean | annotated_cases | correctness | grounding_support | citation_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GEN_llama2:7b | llama2:7b | Q4_0 | COMPLETED | 44 | 0 | 0.5455 | 0.4545 | 1.0 | 0.5455 | 0 | 16737.15 | 37133.925 | 147.9091 | 0 | N/A | N/A | N/A |
| GEN_qwen3.5:4b | qwen3.5:4b | nvfp4 | COMPLETED | 44 | 0 | 0.8182 | 0.1818 | 1.0 | 0.8636 | 0 | 8123.1 | 19174.63 | 94.7727 | 0 | N/A | N/A | N/A |

Correctness, relevance, completeness, grounding and citation support need annotated cases (`annotations` in generation.yaml; null today). With 0 annotated cases they are N/A — BEIR qrels are not reference answers.

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
| A0_AAES | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 648.900 | 0.362 |
| A1_AAES_HARD_FILTER | all | 47 | 0.298 | 0.234 | 0.340 | 0.190 | 0.425 | 0.457 | 0.167 | 0.500 | 0.000 | 0.500 | 0.714 | 507.000 | 0.383 |
| A2_AAES_ORACLE_PROFILE | all | 47 | 0.383 | 0.234 | 0.340 | 0.211 | 0.400 | 0.457 | 0.033 | 0.000 | 0.000 | 0.500 | 0.667 | 586.400 | 0.447 |
| A3_AAES_ALWAYS_CLARIFY | all | 47 | 0.106 | 0.234 | 0.319 | 0.195 | 0.675 | 0.471 | 0.000 | N/A | 0.000 | 1.000 | 1.000 | 228.200 | 0.128 |
| A4_QUESTION_ONLY_AMBIGUITY | all | 47 | 0.404 | 0.489 | 0.532 | 0.307 | 0.300 | 0.471 | 0.000 | 0.000 | 0.000 | 0.250 | 0.789 | 3268.900 | 0.553 |
| A6_AAES_NO_TEMPORAL | all | 47 | 0.277 | 0.255 | 0.362 | 0.202 | 0.425 | 0.471 | 0.000 | 0.000 | 0.000 | 0.500 | 0.769 | 381.800 | 0.362 |
| B0_BASIC_DENSE_RAG | all | 47 | 0.830 | 0.489 | 0.574 | 0.243 | 0.000 | 0.409 | 0.067 | 0.333 | 0.051 | 0.600 | 0.000 | 7693.100 | 1.000 |
| G0_CLOSED_BOOK | all | 47 | 1.000 | 0.447 | 0.532 | 0.154 | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0.000 | 7270.400 | 1.000 |
| G1_ORACLE_CONTEXT | all | 47 | 0.660 | 0.660 | 0.745 | 0.354 | 0.000 | N/A | N/A | 0.000 | 0.065 | 0.000 | 0.000 | 3138.600 | 0.745 |
| R15_SELF_QUERY | all | 47 | 0.787 | 0.596 | 0.681 | 0.310 | 0.000 | 0.366 | 0.033 | 0.000 | 0.162 | 0.600 | 0.000 | 10039.900 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 47 | 0.851 | 0.574 | 0.660 | 0.288 | 0.000 | 0.418 | 0.067 | 0.167 | 0.175 | 0.600 | 0.000 | 7517.000 | 1.000 |
| R5_HYBRID_CROSS_ENCODER | all | 47 | 0.809 | 0.617 | 0.681 | 0.321 | 0.000 | 0.418 | 0.067 | 0.333 | 0.079 | 0.400 | 0.000 | 7412.900 | 1.000 |
| R9S_SCOPE_PREFILTER | all | 47 | 0.872 | 0.574 | 0.660 | 0.289 | 0.000 | 0.464 | 0.067 | 0.167 | 0.098 | 0.400 | 0.000 | 4019.200 | 1.000 |

Per-slice rows: `hyu_dev_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs R15_SELF_QUERY: AER (conditional + temporal, both answered; 1 of 4 cases with inapplicable spans answered by both): diff +0.000 [+0.000, +0.000], p 1.0000, Holm 1.0000 (n=1)
- A0_AAES vs R15_SELF_QUERY: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: diff -0.105 [-0.185, -0.032], p 0.0108, Holm 0.0324 (n=47)
