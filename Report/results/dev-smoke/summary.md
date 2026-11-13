# Benchmark summary — run `dev-smoke`

Git `6cdaf0bc9b` (uncommitted changes) · split `test` · smoke: True · machine: arm64, 16 GB · Ollama 0.40.15

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
| GEN_llama2:7b | llama2:7b | Q4_0 | COMPLETED | 5 | 0 | 0.8 | 0.2 | 1.0 | 0.6 | 0 | 11281.6 | 29445.68 | 161.4 | 0 | N/A | N/A | N/A |
| GEN_qwen3.5:4b | qwen3.5:4b | nvfp4 | COMPLETED | 5 | 0 | 0.8 | 0.2 | 1.0 | 0.8 | 0 | 5243.5 | 12565.34 | 81.4 | 0 | N/A | N/A | N/A |

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
| A0_AAES | all | 5 | 0.000 | 0.000 | 0.400 | 0.000 | 0.667 | 0.300 | N/A | N/A | N/A | N/A | N/A | 155.700 | 0.200 |
| A1_AAES_HARD_FILTER | all | 5 | 0.000 | 0.000 | 0.400 | 0.000 | 0.667 | 0.300 | N/A | N/A | N/A | N/A | N/A | 195.100 | 0.200 |
| A2_AAES_ORACLE_PROFILE | all | 5 | 0.000 | 0.000 | 0.400 | 0.000 | 0.667 | 0.300 | N/A | N/A | N/A | N/A | N/A | 204.000 | 0.200 |
| A3_AAES_ALWAYS_CLARIFY | all | 5 | 0.000 | 0.000 | 0.400 | 0.000 | 1.000 | 0.300 | N/A | N/A | N/A | N/A | N/A | 231.600 | 0.000 |
| A4_QUESTION_ONLY_AMBIGUITY | all | 5 | 0.800 | 0.400 | 0.400 | 0.190 | 0.333 | 0.300 | N/A | N/A | 0.000 | 0.000 | 0.500 | 2643.800 | 0.800 |
| A6_AAES_NO_TEMPORAL | all | 5 | 0.000 | 0.000 | 0.400 | 0.000 | 0.667 | 0.300 | N/A | N/A | N/A | N/A | N/A | 237.600 | 0.200 |
| B0_BASIC_DENSE_RAG | all | 5 | 0.600 | 0.200 | 0.200 | 0.111 | 0.000 | 0.200 | N/A | N/A | 0.000 | 0.000 | 0.000 | 5053.700 | 1.000 |
| G0_CLOSED_BOOK | all | 5 | 1.000 | 0.600 | 0.600 | 0.375 | 0.000 | 0.200 | N/A | N/A | 0.000 | 0.000 | 0.000 | 7691.100 | 1.000 |
| G1_ORACLE_CONTEXT | all | 5 | 0.800 | 0.400 | 0.400 | 0.190 | 0.000 | 0.200 | N/A | N/A | 0.000 | 0.000 | 0.000 | 2482.300 | 1.000 |
| R15_SELF_QUERY | all | 5 | 0.800 | 0.400 | 0.400 | 0.190 | 0.000 | 0.100 | N/A | N/A | 0.250 | 1.000 | 0.000 | 7920.600 | 2.000 |
| R16_PROMPTED_CONDITIONAL | all | 5 | 1.000 | 0.600 | 0.600 | 0.375 | 0.000 | 0.300 | N/A | N/A | 0.000 | 0.000 | 0.000 | 5813.000 | 1.000 |
| R5_HYBRID_CROSS_ENCODER | all | 5 | 1.000 | 0.600 | 0.600 | 0.375 | 0.000 | 0.300 | N/A | N/A | 0.000 | 0.000 | 0.000 | 5786.100 | 1.000 |
| R9S_SCOPE_PREFILTER | all | 5 | 1.000 | 0.600 | 0.600 | 0.375 | 0.000 | 0.300 | N/A | N/A | 0.000 | 0.000 | 0.000 | 2803.400 | 1.000 |

Per-slice rows: `hyu_dev_slices.csv`. Pre-registered comparisons (paired bootstrap 95% CI, permutation p, Holm):

- A0_AAES vs B0_BASIC_DENSE_RAG: AER: NOT_RUN: 0 of 0 cases with inapplicable spans answered by both
- A0_AAES vs B0_BASIC_DENSE_RAG: correctness, unconditional (non-inferiority 3 points): NOT_COMPUTED: needs the validated LLM judge (Appendix F)
- A0_AAES vs A4_QUESTION_ONLY_AMBIGUITY: action macro-F1: diff -0.190 [-0.444, +0.000], p 0.3811, Holm 1.0000 (n=5)
