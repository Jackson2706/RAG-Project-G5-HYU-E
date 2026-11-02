# Benchmark summary — run `main`

Git `203186968a` (uncommitted changes) · split `test` · smoke: False · machine: arm64, 16 GB · Ollama 0.40.13

Task status: COMPLETED: 96, NOT_APPLICABLE: 9, SHARED: 3

All numbers below were computed from the saved per-query results. N/A = not measurable (missing labels, not run, or undefined).

## Report B — Online retrieval, Protocol B — HYU-style chunked retrieval (chunks → BEIR documents)

| dataset | experiment | subset | nDCG@10 | MAP@100 | Recall@100 | P@10 | MRR@10 | retrieval_ms_p50 | delta_nDCG@10_vs_baseline | delta_ci95_low | delta_ci95_high | improved | regressed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arguana | B0_BASIC_DENSE_RAG | all test queries | 0.5981 | 0.5246 | 0.9865 | 0.0854 | 0.5171 | 35.4 | N/A | N/A | N/A | N/A | N/A |
| arguana | R11_TOKEN_BUDGET_SELECTION | all test queries | 0.5981 | 0.5246 | 0.9865 | 0.0854 | 0.5171 | 39.1 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| arguana | R12_SUFFICIENCY_GATE | all test queries | 0.5981 | 0.5246 | 0.9865 | 0.0854 | 0.5171 | 38.8 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| arguana | R13_RANKGPT | first 100 queries | 0.3101 | 0.2866 | 0.98 | 0.049 | 0.2557 | 17695.3 | -0.3337 | -0.4368 | -0.2331 | 20 | 55 |
| arguana | R14_FULL_ADVANCED | first 100 queries | 0.4123 | 0.3444 | 0.99 | 0.069 | 0.328 | 6758.05 | -0.2315 | -0.2978 | -0.1655 | 14 | 57 |
| arguana | R1_BM25 | all test queries | 0.4524 | 0.3755 | 0.931 | 0.073 | 0.3661 | 3.7 | -0.1457 | -0.1651 | -0.1257 | 283 | 709 |
| arguana | R2_HYBRID_RRF_MATCHED_BUDGET | all test queries | 0.5675 | 0.4889 | 0.9872 | 0.0841 | 0.4811 | 38.35 | -0.0306 | -0.0447 | -0.0158 | 365 | 422 |
| arguana | R2_HYBRID_RRF | all test queries | 0.5673 | 0.4888 | 0.9879 | 0.0841 | 0.4808 | 41.0 | -0.0308 | -0.0447 | -0.0159 | 361 | 421 |
| arguana | R3_COVERAGE_RERANK | all test queries | 0.3002 | 0.2523 | 0.9865 | 0.0516 | 0.2338 | 45.4 | -0.2979 | -0.319 | -0.2759 | 181 | 893 |
| arguana | R4_CROSS_ENCODER | all test queries | 0.4159 | 0.3488 | 0.9865 | 0.0682 | 0.334 | 899.7 | -0.1822 | -0.2004 | -0.1629 | 238 | 741 |
| arguana | R5_HYBRID_CROSS_ENCODER | all test queries | 0.4112 | 0.3452 | 0.9879 | 0.0675 | 0.3302 | 944.65 | -0.1869 | -0.2052 | -0.1674 | 234 | 745 |
| arguana | R6_QUERY_REWRITING | first 100 queries | 0.6397 | 0.5848 | 0.98 | 0.084 | 0.5766 | 3673.55 | -0.0041 | -0.0242 | 0.015 | 4 | 5 |
| arguana | R7_MULTI_QUERY | first 100 queries | 0.6372 | 0.5811 | 0.98 | 0.084 | 0.5725 | 3936.2 | -0.0066 | -0.0232 | 0.01 | 2 | 4 |
| arguana | R8_HYDE | first 100 queries | 0.541 | 0.4796 | 0.99 | 0.078 | 0.4674 | 7437.9 | -0.1028 | -0.1683 | -0.0372 | 17 | 39 |
| nfcorpus | B0_BASIC_DENSE_RAG | all test queries | 0.3463 | 0.1584 | 0.3097 | 0.2567 | 0.5316 | 26.2 | N/A | N/A | N/A | N/A | N/A |
| nfcorpus | R11_TOKEN_BUDGET_SELECTION | all test queries | 0.3463 | 0.1584 | 0.3097 | 0.2567 | 0.5316 | 25.4 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| nfcorpus | R12_SUFFICIENCY_GATE | all test queries | 0.3463 | 0.1584 | 0.3097 | 0.2567 | 0.5316 | 26.5 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| nfcorpus | R13_RANKGPT | first 100 queries | 0.3768 | 0.1614 | 0.2613 | 0.271 | 0.5933 | 12885.0 | 0.0221 | 0.007 | 0.0382 | 32 | 16 |
| nfcorpus | R14_FULL_ADVANCED | first 100 queries | 0.3627 | 0.1585 | 0.2616 | 0.263 | 0.5687 | 904.55 | 0.0079 | -0.0273 | 0.0436 | 31 | 26 |
| nfcorpus | R1_BM25 | all test queries | 0.3 | 0.1378 | 0.2343 | 0.208 | 0.5052 | 1.3 | -0.0463 | -0.0678 | -0.025 | 82 | 137 |
| nfcorpus | R2_HYBRID_RRF_MATCHED_BUDGET | all test queries | 0.3576 | 0.1736 | 0.317 | 0.2607 | 0.5692 | 27.0 | 0.0112 | -0.0022 | 0.0255 | 108 | 93 |
| nfcorpus | R2_HYBRID_RRF | all test queries | 0.3576 | 0.174 | 0.3177 | 0.2601 | 0.5699 | 30.0 | 0.0112 | -0.0023 | 0.0258 | 108 | 93 |
| nfcorpus | R3_COVERAGE_RERANK | all test queries | 0.3365 | 0.1595 | 0.3097 | 0.2461 | 0.5303 | 33.4 | -0.0098 | -0.0263 | 0.006 | 84 | 91 |
| nfcorpus | R4_CROSS_ENCODER | all test queries | 0.3539 | 0.1673 | 0.3097 | 0.2517 | 0.5756 | 556.3 | 0.0076 | -0.007 | 0.0223 | 118 | 90 |
| nfcorpus | R5_HYBRID_CROSS_ENCODER | all test queries | 0.358 | 0.171 | 0.3177 | 0.2526 | 0.582 | 529.1 | 0.0116 | -0.0046 | 0.0282 | 120 | 92 |
| nfcorpus | R6_QUERY_REWRITING | first 100 queries | 0.3547 | 0.1509 | 0.2613 | 0.264 | 0.5322 | 332.4 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| nfcorpus | R7_MULTI_QUERY | first 100 queries | 0.3586 | 0.1553 | 0.2676 | 0.263 | 0.5519 | 954.25 | 0.0039 | -0.0056 | 0.0139 | 23 | 15 |
| nfcorpus | R8_HYDE | first 100 queries | 0.3633 | 0.1581 | 0.2831 | 0.27 | 0.5584 | 4052.9 | 0.0086 | -0.0185 | 0.0369 | 27 | 36 |
| scifact | B0_BASIC_DENSE_RAG | all test queries | 0.7156 | 0.6758 | 0.9383 | 0.0953 | 0.6812 | 22.7 | N/A | N/A | N/A | N/A | N/A |
| scifact | R11_TOKEN_BUDGET_SELECTION | all test queries | 0.7156 | 0.6758 | 0.9383 | 0.0953 | 0.6812 | 22.9 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| scifact | R12_SUFFICIENCY_GATE | all test queries | 0.7156 | 0.6758 | 0.9383 | 0.0953 | 0.6812 | 22.7 | 0.0 | 0.0 | 0.0 | 0 | 0 |
| scifact | R13_RANKGPT | first 100 queries | 0.7083 | 0.6613 | 0.92 | 0.097 | 0.6636 | 13410.1 | -0.0045 | -0.0463 | 0.0365 | 18 | 15 |
| scifact | R14_FULL_ADVANCED | first 100 queries | 0.7147 | 0.684 | 0.96 | 0.091 | 0.6889 | 1644.8 | 0.0018 | -0.0483 | 0.0521 | 19 | 16 |
| scifact | R1_BM25 | all test queries | 0.6505 | 0.6147 | 0.8726 | 0.0847 | 0.6203 | 2.7 | -0.0651 | -0.102 | -0.0294 | 48 | 87 |
| scifact | R2_HYBRID_RRF_MATCHED_BUDGET | all test queries | 0.7109 | 0.675 | 0.9617 | 0.0933 | 0.6804 | 24.6 | -0.0047 | -0.0312 | 0.0217 | 59 | 46 |
| scifact | R2_HYBRID_RRF | all test queries | 0.7109 | 0.675 | 0.9617 | 0.0933 | 0.6804 | 28.1 | -0.0047 | -0.0312 | 0.0217 | 59 | 46 |
| scifact | R3_COVERAGE_RERANK | all test queries | 0.6206 | 0.5864 | 0.9383 | 0.082 | 0.5899 | 29.3 | -0.0949 | -0.1324 | -0.0597 | 42 | 92 |
| scifact | R4_CROSS_ENCODER | all test queries | 0.7005 | 0.6653 | 0.9383 | 0.092 | 0.6686 | 533.05 | -0.0151 | -0.0426 | 0.0114 | 52 | 60 |
| scifact | R5_HYBRID_CROSS_ENCODER | all test queries | 0.6991 | 0.6676 | 0.9617 | 0.0907 | 0.6695 | 547.25 | -0.0165 | -0.0447 | 0.0114 | 52 | 61 |
| scifact | R6_QUERY_REWRITING | first 100 queries | 0.7259 | 0.691 | 0.93 | 0.096 | 0.6943 | 882.4 | 0.0131 | -0.0118 | 0.0386 | 12 | 5 |
| scifact | R7_MULTI_QUERY | first 100 queries | 0.7134 | 0.6786 | 0.92 | 0.095 | 0.6771 | 2034.9 | 0.0006 | -0.024 | 0.0264 | 10 | 7 |
| scifact | R8_HYDE | first 100 queries | 0.7256 | 0.6713 | 0.92 | 0.1 | 0.6859 | 4439.45 | 0.0128 | -0.0374 | 0.0673 | 22 | 18 |

Best nDCG@10 per dataset (all queries only; LLM methods ran on a subset and are compared with B0 on that subset above):
- **arguana**: B0_BASIC_DENSE_RAG (0.5981) vs B0 0.5981
- **nfcorpus**: R5_HYBRID_CROSS_ENCODER (0.3580) vs B0 0.3463
- **scifact**: B0_BASIC_DENSE_RAG (0.7156) vs B0 0.7156

## Report B — Online retrieval, Protocol A — BEIR documents as units

| dataset | experiment | subset | nDCG@10 | MAP@100 | Recall@100 | P@10 | MRR@10 | retrieval_ms_p50 | delta_nDCG@10_vs_baseline | delta_ci95_low | delta_ci95_high | improved | regressed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arguana | B0_BASIC_DENSE_RAG | all test queries | 0.6046 | 0.5312 | 0.9879 | 0.086 | 0.5238 | 33.5 | N/A | N/A | N/A | N/A | N/A |
| arguana | R1_BM25 | all test queries | 0.4257 | 0.3511 | 0.9232 | 0.0699 | 0.3407 | 2.0 | -0.1789 | -0.1988 | -0.1587 | 262 | 762 |
| arguana | R2_HYBRID_RRF | all test queries | 0.5506 | 0.4715 | 0.9865 | 0.0829 | 0.4631 | 35.45 | -0.054 | -0.0688 | -0.0386 | 333 | 505 |
| arguana | R3_COVERAGE_RERANK | all test queries | 0.2146 | 0.1812 | 0.9879 | 0.0401 | 0.1578 | 42.4 | -0.39 | -0.4098 | -0.3693 | 116 | 1009 |
| arguana | R4_CROSS_ENCODER | all test queries | 0.4163 | 0.3497 | 0.9879 | 0.0681 | 0.3348 | 884.15 | -0.1883 | -0.2058 | -0.169 | 225 | 750 |
| arguana | R5_HYBRID_CROSS_ENCODER | all test queries | 0.4133 | 0.3466 | 0.9865 | 0.0679 | 0.3316 | 975.8 | -0.1913 | -0.2087 | -0.172 | 219 | 755 |
| nfcorpus | B0_BASIC_DENSE_RAG | all test queries | 0.3435 | 0.1558 | 0.311 | 0.2576 | 0.5287 | 22.9 | N/A | N/A | N/A | N/A | N/A |
| nfcorpus | R1_BM25 | all test queries | 0.3079 | 0.1384 | 0.2361 | 0.2167 | 0.5168 | 0.8 | -0.0356 | -0.0581 | -0.0138 | 85 | 128 |
| nfcorpus | R2_HYBRID_RRF | all test queries | 0.3575 | 0.1726 | 0.315 | 0.2601 | 0.5682 | 24.5 | 0.014 | -0.0005 | 0.0291 | 106 | 93 |
| nfcorpus | R3_COVERAGE_RERANK | all test queries | 0.3305 | 0.158 | 0.311 | 0.2399 | 0.5308 | 29.6 | -0.013 | -0.0301 | 0.0031 | 79 | 90 |
| nfcorpus | R4_CROSS_ENCODER | all test queries | 0.3484 | 0.1663 | 0.311 | 0.2458 | 0.5709 | 871.9 | 0.0049 | -0.011 | 0.0213 | 105 | 99 |
| nfcorpus | R5_HYBRID_CROSS_ENCODER | all test queries | 0.3525 | 0.1708 | 0.315 | 0.2467 | 0.5792 | 947.9 | 0.009 | -0.0094 | 0.0264 | 110 | 101 |
| scifact | B0_BASIC_DENSE_RAG | all test queries | 0.7127 | 0.6736 | 0.9417 | 0.0943 | 0.6822 | 21.8 | N/A | N/A | N/A | N/A | N/A |
| scifact | R1_BM25 | all test queries | 0.6645 | 0.6255 | 0.8859 | 0.0873 | 0.6326 | 1.0 | -0.0482 | -0.0856 | -0.0134 | 53 | 82 |
| scifact | R2_HYBRID_RRF | all test queries | 0.7078 | 0.6725 | 0.965 | 0.0927 | 0.6779 | 22.6 | -0.0049 | -0.0314 | 0.0207 | 52 | 48 |
| scifact | R3_COVERAGE_RERANK | all test queries | 0.6063 | 0.574 | 0.9417 | 0.0797 | 0.5776 | 26.7 | -0.1065 | -0.1447 | -0.0721 | 34 | 90 |
| scifact | R4_CROSS_ENCODER | all test queries | 0.6944 | 0.6548 | 0.9417 | 0.092 | 0.6643 | 821.2 | -0.0183 | -0.0455 | 0.0083 | 48 | 62 |
| scifact | R5_HYBRID_CROSS_ENCODER | all test queries | 0.6892 | 0.6516 | 0.965 | 0.0913 | 0.6587 | 895.35 | -0.0235 | -0.0518 | 0.0044 | 52 | 66 |

Best nDCG@10 per dataset (all queries only; LLM methods ran on a subset and are compared with B0 on that subset above):
- **arguana**: B0_BASIC_DENSE_RAG (0.6046) vs B0 0.6046
- **nfcorpus**: R2_HYBRID_RRF (0.3575) vs B0 0.3435
- **scifact**: B0_BASIC_DENSE_RAG (0.7127) vs B0 0.7127

Not completed online tasks:

| dataset | protocol | experiment | status | reason |
|---|---|---|---|---|
| arguana | - | PROPOSED_APPROACH | NOT_APPLICABLE | Reserved: the team has not defined its proposed approach yet |
| arguana | - | R0_DENSE | SHARED | identical configuration to B0_BASIC_DENSE_RAG; its results apply |
| arguana | - | R10_POSTFILTERING | NOT_APPLICABLE | BEIR has no eligibility metadata; evaluated on the HYU metadata fixture instead |
| arguana | - | R9_PREFILTERING | NOT_APPLICABLE | BEIR has no eligibility metadata; evaluated on the HYU metadata fixture instead |
| nfcorpus | - | PROPOSED_APPROACH | NOT_APPLICABLE | Reserved: the team has not defined its proposed approach yet |
| nfcorpus | - | R0_DENSE | SHARED | identical configuration to B0_BASIC_DENSE_RAG; its results apply |
| nfcorpus | - | R10_POSTFILTERING | NOT_APPLICABLE | BEIR has no eligibility metadata; evaluated on the HYU metadata fixture instead |
| nfcorpus | - | R9_PREFILTERING | NOT_APPLICABLE | BEIR has no eligibility metadata; evaluated on the HYU metadata fixture instead |
| scifact | - | PROPOSED_APPROACH | NOT_APPLICABLE | Reserved: the team has not defined its proposed approach yet |
| scifact | - | R0_DENSE | SHARED | identical configuration to B0_BASIC_DENSE_RAG; its results apply |
| scifact | - | R10_POSTFILTERING | NOT_APPLICABLE | BEIR has no eligibility metadata; evaluated on the HYU metadata fixture instead |
| scifact | - | R9_PREFILTERING | NOT_APPLICABLE | BEIR has no eligibility metadata; evaluated on the HYU metadata fixture instead |

## Report A — Offline comparison

| dataset | protocol | experiment | chunker | chunk_size | chunk_overlap | embedding | chunks | nDCG@10 | Recall@100 | index_build_s | mongodb_storage_bytes | qdrant_raw_vector_bytes | source_spans_invalid | truncated_by_embedder | hnsw_built | delta_nDCG@10_vs_baseline | delta_ci95_low | delta_ci95_high |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arguana | B | O0_SECTION_AWARE_256_32 | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 11147 | 0.5981 | 0.9865 | 68.8057 | 8253440 | 17121792 | 0 | 0 | False | N/A | N/A | N/A |
| arguana | B | O1_FIXED_256_32 | fixed_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 11147 | 0.5988 | 0.9865 | 166.6164 | 8249344 | 17121792 | 0 | 0 | False | 0.0007 | -0.0007 | 0.0023 |
| arguana | B | O2_NO_OVERLAP | section_tokens | 256 | 0 | BAAI/bge-small-en-v1.5 | 11077 | 0.6016 | 0.9865 | 83.3057 | 8253440 | 17014272 | 0 | 0 | False | 0.0035 | 0.0003 | 0.0067 |
| arguana | B | O3_SMALL_CHUNKS | section_tokens | 128 | 32 | BAAI/bge-small-en-v1.5 | 20066 | 0.5374 | 0.9801 | 694.4549 | 9527296 | 30821376 | 0 | 0 | False | -0.0607 | -0.0731 | -0.0488 |
| arguana | B | O4_LARGE_CHUNKS | section_tokens | 512 | 32 | BAAI/bge-small-en-v1.5 | 8861 | 0.6037 | 0.9879 | 66.7695 | 7991296 | 13610496 | 0 | 188 | False | 0.0056 | 0.0009 | 0.0108 |
| arguana | B | O5_RECURSIVE | recursive | 256 | 32 | BAAI/bge-small-en-v1.5 | 11163 | 0.5962 | 0.9858 | 81.3796 | 8265728 | 17146368 | 0 | 0 | False | -0.0019 | -0.006 | 0.0026 |
| arguana | B | O6_ALTERNATIVE_EMBEDDING | section_tokens | 256 | 32 | sentence-transformers/all-MiniLM-L6-v2 | 11147 | 0.4942 | 0.9787 | 37.9178 | 8249344 | 17121792 | 0 | 2517 | False | -0.1039 | -0.1212 | -0.0868 |
| arguana | B | O7_EXACT_SEARCH | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 11147 | 0.5987 | 0.9865 | 77.6176 | 8253440 | 17121792 | 0 | 0 | True | 0.0006 | -0.0008 | 0.0022 |
| arguana | B | O8_HNSW_ANN | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 11147 | 0.5987 | 0.9865 | 77.6176 | 8253440 | 17121792 | 0 | 0 | True | 0.0006 | -0.0008 | 0.0022 |
| arguana | A | PA_WHOLE_DOCUMENT | whole_document | N/A | N/A | BAAI/bge-small-en-v1.5 | 8674 | 0.6046 | 0.9879 | 67.1735 | 7974912 | 13323264 | 0 | 181 | False | N/A | N/A | N/A |
| nfcorpus | B | O0_SECTION_AWARE_256_32 | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 7012 | 0.3463 | 0.3097 | 68.4674 | 12288 | 10770432 | 0 | 0 | False | N/A | N/A | N/A |
| nfcorpus | B | O1_FIXED_256_32 | fixed_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 7012 | 0.3464 | 0.3097 | 80.7989 | 12288 | 10770432 | 0 | 0 | False | 0.0001 | -0.0011 | 0.001 |
| nfcorpus | B | O2_NO_OVERLAP | section_tokens | 256 | 0 | BAAI/bge-small-en-v1.5 | 6843 | 0.3465 | 0.3053 | 68.9611 | 12288 | 10510848 | 0 | 0 | False | 0.0002 | -0.0053 | 0.0053 |
| nfcorpus | B | O3_SMALL_CHUNKS | section_tokens | 128 | 32 | BAAI/bge-small-en-v1.5 | 14016 | 0.3499 | 0.3032 | 681.6207 | 5988352 | 21528576 | 0 | 0 | False | 0.0035 | -0.0088 | 0.016 |
| nfcorpus | B | O4_LARGE_CHUNKS | section_tokens | 512 | 32 | BAAI/bge-small-en-v1.5 | 3968 | 0.3431 | 0.3126 | 52.8814 | 12288 | 6094848 | 0 | 344 | False | -0.0033 | -0.0103 | 0.0036 |
| nfcorpus | B | O5_RECURSIVE | recursive | 256 | 32 | BAAI/bge-small-en-v1.5 | 7122 | 0.3487 | 0.3083 | 66.3933 | 12288 | 10939392 | 0 | 0 | False | 0.0024 | -0.0029 | 0.0081 |
| nfcorpus | B | O6_ALTERNATIVE_EMBEDDING | section_tokens | 256 | 32 | sentence-transformers/all-MiniLM-L6-v2 | 7012 | 0.319 | 0.3123 | 31.3628 | 12288 | 10770432 | 0 | 3416 | False | -0.0274 | -0.0421 | -0.013 |
| nfcorpus | B | O7_EXACT_SEARCH | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 7012 | 0.3465 | 0.3097 | 68.61 | 4857856 | 10770432 | 0 | 0 | True | 0.0001 | -0.001 | 0.0011 |
| nfcorpus | B | O8_HNSW_ANN | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 7012 | 0.3465 | 0.3097 | 68.61 | 4857856 | 10770432 | 0 | 0 | True | 0.0001 | -0.001 | 0.0011 |
| nfcorpus | A | PA_WHOLE_DOCUMENT | whole_document | N/A | N/A | BAAI/bge-small-en-v1.5 | 3633 | 0.3435 | 0.311 | 51.9497 | 12288 | 5580288 | 0 | 330 | False | N/A | N/A | N/A |
| scifact | B | O0_SECTION_AWARE_256_32 | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 9564 | 0.7156 | 0.9383 | 115.4667 | 7057408 | 14690304 | 0 | 0 | False | N/A | N/A | N/A |
| scifact | B | O1_FIXED_256_32 | fixed_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 9564 | 0.7156 | 0.9383 | 108.7788 | 7053312 | 14690304 | 0 | 0 | False | 0.0 | 0.0 | 0.0 |
| scifact | B | O2_NO_OVERLAP | section_tokens | 256 | 0 | BAAI/bge-small-en-v1.5 | 9356 | 0.7057 | 0.94 | 106.7187 | 6848512 | 14370816 | 0 | 0 | False | -0.0099 | -0.022 | 0.0023 |
| scifact | B | O3_SMALL_CHUNKS | section_tokens | 128 | 32 | BAAI/bge-small-en-v1.5 | 18944 | 0.7132 | 0.9567 | 713.4233 | 8511488 | 29097984 | 0 | 0 | False | -0.0024 | -0.0229 | 0.0179 |
| scifact | B | O4_LARGE_CHUNKS | section_tokens | 512 | 32 | BAAI/bge-small-en-v1.5 | 5648 | 0.7119 | 0.9417 | 71.0115 | 12288 | 8675328 | 0 | 471 | False | -0.0037 | -0.0184 | 0.0102 |
| scifact | B | O5_RECURSIVE | recursive | 256 | 32 | BAAI/bge-small-en-v1.5 | 9637 | 0.7104 | 0.9433 | 94.7326 | 12288 | 14802432 | 0 | 0 | False | -0.0052 | -0.0192 | 0.0087 |
| scifact | B | O6_ALTERNATIVE_EMBEDDING | section_tokens | 256 | 32 | sentence-transformers/all-MiniLM-L6-v2 | 9564 | 0.6583 | 0.93 | 53.7759 | 16384 | 14690304 | 0 | 4423 | False | -0.0573 | -0.086 | -0.029 |
| scifact | B | O7_EXACT_SEARCH | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 9564 | 0.7156 | 0.9383 | 97.2737 | 7057408 | 14690304 | 0 | 0 | True | 0.0 | 0.0 | 0.0 |
| scifact | B | O8_HNSW_ANN | section_tokens | 256 | 32 | BAAI/bge-small-en-v1.5 | 9564 | 0.7156 | 0.9383 | 97.2737 | 7057408 | 14690304 | 0 | 0 | True | 0.0 | 0.0 | 0.0 |
| scifact | A | PA_WHOLE_DOCUMENT | whole_document | N/A | N/A | BAAI/bge-small-en-v1.5 | 5183 | 0.7127 | 0.9417 | 79.3953 | 12288 | 7961088 | 0 | 455 | False | N/A | N/A | N/A |

### Exact (O7) vs HNSW (O8) on identical vectors and queries

| dataset | queries | ann_recall@10_vs_exact | ann_recall@100_vs_exact | exact_search_ms_p50 | hnsw_search_ms_p50 | exact_search_ms_p95 | hnsw_search_ms_p95 | repetitions_per_query |
|---|---|---|---|---|---|---|---|---|
| arguana | 1406 | 1.0 | 1.0 | 6.56 | 6.12 | 9.323 | 8.5 | 3 |
| nfcorpus | 323 | 1.0 | 1.0 | 5.74 | 5.55 | 7.274 | 7.0 | 3 |
| scifact | 300 | 1.0 | 1.0 | 5.61 | 5.525 | 6.8205 | 6.73 | 3 |

Latency is Qdrant's measured query time over HTTP on this machine; HNSW only counts when the manifest says the graph was built.

## Controlled fixture (5 synthetic HYU documents; author-written labels — not a benchmark)

| experiment | status | cases | candidate_cutoff | target_hit_rate | ineligible_returned_rate | starved_rate | empty_rate | returned_units_mean |
|---|---|---|---|---|---|---|---|---|
| R0_DENSE | COMPLETED | 10 | 2 | 1.0 | 0.3 | 0.0 | 0.0 | 2.0 |
| R9_PREFILTERING | COMPLETED | 10 | 2 | 1.0 | 0.0 | 0.0 | 0.0 | 2.0 |
| R10_POSTFILTERING | COMPLETED | 10 | 2 | 1.0 | 0.0 | 0.3 | 0.3 | 1.4 |

| experiment | label_source | signal | threshold | cases | TP | FP | TN | FN | accuracy | precision | recall | false_positive_rate | false_negative_rate | abstention_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R12_SUFFICIENCY_GATE | author-written fixture labels (answerable + relevant evidence selected) | query_coverage | 0.3 | 14 | 11 | 2 | 1 | 0 | 0.8571 | 0.8462 | 1.0 | 0.6667 | 0.0 | 0.0714 |

## Report C — Generation (same cached evidence for both backbones)

| experiment | model | quantization | status | cases | failed | answered_rate | abstention_rate | marker_validity_mean | answers_citing_a_source_rate | invalid_markers_total | generation_ms_p50 | generation_ms_p95 | output_tokens_mean | annotated_cases | correctness | grounding_support | citation_precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GEN_llama2:7b | llama2:7b | Q4_0 | COMPLETED | 44 | 0 | 0.6818 | 0.3182 | 1.0 | 0.5 | 0 | 20983.9 | 48447.745 | 166.7391 | 0 | N/A | N/A | N/A |
| GEN_qwen3.5:4b | qwen3.5:4b | nvfp4 | COMPLETED | 44 | 0 | 0.8182 | 0.1818 | 1.0 | 0.8636 | 0 | 6427.85 | 16706.485 | 94.7727 | 0 | N/A | N/A | N/A |

Correctness, relevance, completeness, grounding and citation support need annotated cases (evaluation/annotations/). With 0 annotated cases they are N/A — BEIR qrels are not reference answers.

## Report D — Failure categories (earliest observable stage)

| dataset | protocol | experiment | category | queries |
|---|---|---|---|---|
| arguana | A | B0_BASIC_DENSE_RAG | Relevant source not retrieved | 17 |
| arguana | A | B0_BASIC_DENSE_RAG | Relevant source ranked too low | 180 |
| arguana | A | B0_BASIC_DENSE_RAG | Relevant source retrieved but dropped by Evidence Selection | 450 |
| arguana | A | R1_BM25 | Relevant source not retrieved | 108 |
| arguana | A | R1_BM25 | Relevant source ranked too low | 315 |
| arguana | A | R1_BM25 | Relevant source retrieved but dropped by Evidence Selection | 509 |
| arguana | A | R2_HYBRID_RRF | Relevant source not retrieved | 19 |
| arguana | A | R2_HYBRID_RRF | Relevant source ranked too low | 222 |
| arguana | A | R2_HYBRID_RRF | Relevant source retrieved but dropped by Evidence Selection | 488 |
| arguana | A | R3_COVERAGE_RERANK | Relevant source not retrieved | 17 |
| arguana | A | R3_COVERAGE_RERANK | Relevant source ranked too low | 825 |
| arguana | A | R3_COVERAGE_RERANK | Relevant source retrieved but dropped by Evidence Selection | 361 |
| arguana | A | R4_CROSS_ENCODER | Relevant source not retrieved | 17 |
| arguana | A | R4_CROSS_ENCODER | Relevant source ranked too low | 432 |
| arguana | A | R4_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 505 |
| arguana | A | R5_HYBRID_CROSS_ENCODER | Relevant source not retrieved | 19 |
| arguana | A | R5_HYBRID_CROSS_ENCODER | Relevant source ranked too low | 433 |
| arguana | A | R5_HYBRID_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 506 |
| arguana | B | B0_BASIC_DENSE_RAG | Relevant source not retrieved | 18 |
| arguana | B | B0_BASIC_DENSE_RAG | Relevant source ranked too low | 187 |
| arguana | B | B0_BASIC_DENSE_RAG | Relevant source retrieved but dropped by Evidence Selection | 492 |
| arguana | B | O0_SECTION_AWARE_256_32 | Relevant source not retrieved | 18 |
| arguana | B | O0_SECTION_AWARE_256_32 | Relevant source ranked too low | 187 |
| arguana | B | O0_SECTION_AWARE_256_32 | Relevant source retrieved but dropped by Evidence Selection | 492 |
| arguana | B | O1_FIXED_256_32 | Relevant source not retrieved | 18 |
| arguana | B | O1_FIXED_256_32 | Relevant source ranked too low | 187 |
| arguana | B | O1_FIXED_256_32 | Relevant source retrieved but dropped by Evidence Selection | 490 |
| arguana | B | O2_NO_OVERLAP | Relevant source not retrieved | 18 |
| arguana | B | O2_NO_OVERLAP | Relevant source ranked too low | 181 |
| arguana | B | O2_NO_OVERLAP | Relevant source retrieved but dropped by Evidence Selection | 480 |
| arguana | B | O3_SMALL_CHUNKS | Relevant source not retrieved | 28 |
| arguana | B | O3_SMALL_CHUNKS | Relevant source ranked too low | 260 |
| arguana | B | O3_SMALL_CHUNKS | Relevant source retrieved but dropped by Evidence Selection | 732 |
| arguana | B | O4_LARGE_CHUNKS | Relevant source not retrieved | 16 |
| arguana | B | O4_LARGE_CHUNKS | Relevant source ranked too low | 182 |
| arguana | B | O4_LARGE_CHUNKS | Relevant source retrieved but dropped by Evidence Selection | 450 |
| arguana | B | O5_RECURSIVE | Relevant source not retrieved | 19 |
| arguana | B | O5_RECURSIVE | Relevant source ranked too low | 182 |
| arguana | B | O5_RECURSIVE | Relevant source retrieved but dropped by Evidence Selection | 501 |
| arguana | B | O6_ALTERNATIVE_EMBEDDING | Relevant source not retrieved | 30 |
| arguana | B | O6_ALTERNATIVE_EMBEDDING | Relevant source ranked too low | 285 |
| arguana | B | O6_ALTERNATIVE_EMBEDDING | Relevant source retrieved but dropped by Evidence Selection | 558 |
| arguana | B | O7_EXACT_SEARCH | Relevant source not retrieved | 18 |
| arguana | B | O7_EXACT_SEARCH | Relevant source ranked too low | 187 |
| arguana | B | O7_EXACT_SEARCH | Relevant source retrieved but dropped by Evidence Selection | 491 |
| arguana | B | O8_HNSW_ANN | Relevant source not retrieved | 18 |
| arguana | B | O8_HNSW_ANN | Relevant source ranked too low | 187 |
| arguana | B | O8_HNSW_ANN | Relevant source retrieved but dropped by Evidence Selection | 491 |
| arguana | B | R11_TOKEN_BUDGET_SELECTION | Relevant source not retrieved | 18 |
| arguana | B | R11_TOKEN_BUDGET_SELECTION | Relevant source ranked too low | 187 |
| arguana | B | R11_TOKEN_BUDGET_SELECTION | Relevant source retrieved but dropped by Evidence Selection | 32 |
| arguana | B | R12_SUFFICIENCY_GATE | Relevant source not retrieved | 18 |
| arguana | B | R12_SUFFICIENCY_GATE | Relevant source ranked too low | 187 |
| arguana | B | R12_SUFFICIENCY_GATE | Relevant source retrieved but dropped by Evidence Selection | 492 |
| arguana | B | R13_RANKGPT | Relevant source not retrieved | 2 |
| arguana | B | R13_RANKGPT | Relevant source ranked too low | 49 |
| arguana | B | R13_RANKGPT | Relevant source retrieved but dropped by Evidence Selection | 26 |
| arguana | B | R14_FULL_ADVANCED | Relevant source not retrieved | 1 |
| arguana | B | R14_FULL_ADVANCED | Relevant source ranked too low | 30 |
| arguana | B | R14_FULL_ADVANCED | Relevant source retrieved but dropped by Evidence Selection | 39 |
| arguana | B | R1_BM25 | Relevant source not retrieved | 96 |
| arguana | B | R1_BM25 | Relevant source ranked too low | 284 |
| arguana | B | R1_BM25 | Relevant source retrieved but dropped by Evidence Selection | 615 |
| arguana | B | R2_HYBRID_RRF | Relevant source not retrieved | 17 |
| arguana | B | R2_HYBRID_RRF | Relevant source ranked too low | 206 |
| arguana | B | R2_HYBRID_RRF | Relevant source retrieved but dropped by Evidence Selection | 556 |
| arguana | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source not retrieved | 17 |
| arguana | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source ranked too low | 206 |
| arguana | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source retrieved but dropped by Evidence Selection | 556 |
| arguana | B | R3_COVERAGE_RERANK | Relevant source not retrieved | 18 |
| arguana | B | R3_COVERAGE_RERANK | Relevant source ranked too low | 662 |
| arguana | B | R3_COVERAGE_RERANK | Relevant source retrieved but dropped by Evidence Selection | 451 |
| arguana | B | R4_CROSS_ENCODER | Relevant source not retrieved | 18 |
| arguana | B | R4_CROSS_ENCODER | Relevant source ranked too low | 429 |
| arguana | B | R4_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 522 |
| arguana | B | R5_HYBRID_CROSS_ENCODER | Relevant source not retrieved | 17 |
| arguana | B | R5_HYBRID_CROSS_ENCODER | Relevant source ranked too low | 440 |
| arguana | B | R5_HYBRID_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 510 |
| arguana | B | R6_QUERY_REWRITING | Relevant source not retrieved | 2 |
| arguana | B | R6_QUERY_REWRITING | Relevant source ranked too low | 14 |
| arguana | B | R6_QUERY_REWRITING | Relevant source retrieved but dropped by Evidence Selection | 28 |
| arguana | B | R7_MULTI_QUERY | Relevant source not retrieved | 2 |
| arguana | B | R7_MULTI_QUERY | Relevant source ranked too low | 14 |
| arguana | B | R7_MULTI_QUERY | Relevant source retrieved but dropped by Evidence Selection | 29 |
| arguana | B | R8_HYDE | Relevant source not retrieved | 1 |
| arguana | B | R8_HYDE | Relevant source ranked too low | 21 |
| arguana | B | R8_HYDE | Relevant source retrieved but dropped by Evidence Selection | 36 |
| hyu_fixture | - | R10_POSTFILTERING | Candidate starvation after Postfiltering | 3 |
| hyu_fixture | - | R12_SUFFICIENCY_GATE | Incorrect proceed/abstain decision | 2 |
| nfcorpus | A | B0_BASIC_DENSE_RAG | Relevant source not retrieved | 50 |
| nfcorpus | A | B0_BASIC_DENSE_RAG | Relevant source ranked too low | 49 |
| nfcorpus | A | B0_BASIC_DENSE_RAG | Relevant source retrieved but dropped by Evidence Selection | 25 |
| nfcorpus | A | R1_BM25 | Relevant source not retrieved | 73 |
| nfcorpus | A | R1_BM25 | Relevant source ranked too low | 29 |
| nfcorpus | A | R1_BM25 | Relevant source retrieved but dropped by Evidence Selection | 38 |
| nfcorpus | A | R2_HYBRID_RRF | Relevant source not retrieved | 50 |
| nfcorpus | A | R2_HYBRID_RRF | Relevant source ranked too low | 39 |
| nfcorpus | A | R2_HYBRID_RRF | Relevant source retrieved but dropped by Evidence Selection | 27 |
| nfcorpus | A | R3_COVERAGE_RERANK | Relevant source not retrieved | 50 |
| nfcorpus | A | R3_COVERAGE_RERANK | Relevant source ranked too low | 49 |
| nfcorpus | A | R3_COVERAGE_RERANK | Relevant source retrieved but dropped by Evidence Selection | 28 |
| nfcorpus | A | R4_CROSS_ENCODER | Relevant source not retrieved | 50 |
| nfcorpus | A | R4_CROSS_ENCODER | Relevant source ranked too low | 42 |
| nfcorpus | A | R4_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 31 |
| nfcorpus | A | R5_HYBRID_CROSS_ENCODER | Relevant source not retrieved | 50 |
| nfcorpus | A | R5_HYBRID_CROSS_ENCODER | Relevant source ranked too low | 38 |
| nfcorpus | A | R5_HYBRID_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 26 |
| nfcorpus | B | B0_BASIC_DENSE_RAG | Relevant source not retrieved | 51 |
| nfcorpus | B | B0_BASIC_DENSE_RAG | Relevant source ranked too low | 40 |
| nfcorpus | B | B0_BASIC_DENSE_RAG | Relevant source retrieved but dropped by Evidence Selection | 44 |
| nfcorpus | B | O0_SECTION_AWARE_256_32 | Relevant source not retrieved | 51 |
| nfcorpus | B | O0_SECTION_AWARE_256_32 | Relevant source ranked too low | 40 |
| nfcorpus | B | O0_SECTION_AWARE_256_32 | Relevant source retrieved but dropped by Evidence Selection | 44 |
| nfcorpus | B | O1_FIXED_256_32 | Relevant source not retrieved | 51 |
| nfcorpus | B | O1_FIXED_256_32 | Relevant source ranked too low | 40 |
| nfcorpus | B | O1_FIXED_256_32 | Relevant source retrieved but dropped by Evidence Selection | 44 |
| nfcorpus | B | O2_NO_OVERLAP | Relevant source not retrieved | 53 |
| nfcorpus | B | O2_NO_OVERLAP | Relevant source ranked too low | 38 |
| nfcorpus | B | O2_NO_OVERLAP | Relevant source retrieved but dropped by Evidence Selection | 38 |
| nfcorpus | B | O3_SMALL_CHUNKS | Relevant source not retrieved | 52 |
| nfcorpus | B | O3_SMALL_CHUNKS | Relevant source ranked too low | 43 |
| nfcorpus | B | O3_SMALL_CHUNKS | Relevant source retrieved but dropped by Evidence Selection | 43 |
| nfcorpus | B | O4_LARGE_CHUNKS | Relevant source not retrieved | 50 |
| nfcorpus | B | O4_LARGE_CHUNKS | Relevant source ranked too low | 49 |
| nfcorpus | B | O4_LARGE_CHUNKS | Relevant source retrieved but dropped by Evidence Selection | 27 |
| nfcorpus | B | O5_RECURSIVE | Relevant source not retrieved | 52 |
| nfcorpus | B | O5_RECURSIVE | Relevant source ranked too low | 45 |
| nfcorpus | B | O5_RECURSIVE | Relevant source retrieved but dropped by Evidence Selection | 29 |
| nfcorpus | B | O6_ALTERNATIVE_EMBEDDING | Relevant source not retrieved | 53 |
| nfcorpus | B | O6_ALTERNATIVE_EMBEDDING | Relevant source ranked too low | 44 |
| nfcorpus | B | O6_ALTERNATIVE_EMBEDDING | Relevant source retrieved but dropped by Evidence Selection | 54 |
| nfcorpus | B | O7_EXACT_SEARCH | Relevant source not retrieved | 51 |
| nfcorpus | B | O7_EXACT_SEARCH | Relevant source ranked too low | 40 |
| nfcorpus | B | O7_EXACT_SEARCH | Relevant source retrieved but dropped by Evidence Selection | 44 |
| nfcorpus | B | O8_HNSW_ANN | Relevant source not retrieved | 51 |
| nfcorpus | B | O8_HNSW_ANN | Relevant source ranked too low | 40 |
| nfcorpus | B | O8_HNSW_ANN | Relevant source retrieved but dropped by Evidence Selection | 44 |
| nfcorpus | B | R11_TOKEN_BUDGET_SELECTION | Relevant source not retrieved | 51 |
| nfcorpus | B | R11_TOKEN_BUDGET_SELECTION | Relevant source ranked too low | 40 |
| nfcorpus | B | R11_TOKEN_BUDGET_SELECTION | Relevant source retrieved but dropped by Evidence Selection | 10 |
| nfcorpus | B | R12_SUFFICIENCY_GATE | Relevant source not retrieved | 51 |
| nfcorpus | B | R12_SUFFICIENCY_GATE | Relevant source ranked too low | 40 |
| nfcorpus | B | R12_SUFFICIENCY_GATE | Relevant source retrieved but dropped by Evidence Selection | 44 |
| nfcorpus | B | R13_RANKGPT | Relevant source not retrieved | 24 |
| nfcorpus | B | R13_RANKGPT | Relevant source ranked too low | 9 |
| nfcorpus | B | R13_RANKGPT | Relevant source retrieved but dropped by Evidence Selection | 5 |
| nfcorpus | B | R14_FULL_ADVANCED | Relevant source not retrieved | 23 |
| nfcorpus | B | R14_FULL_ADVANCED | Relevant source ranked too low | 9 |
| nfcorpus | B | R14_FULL_ADVANCED | Relevant source retrieved but dropped by Evidence Selection | 2 |
| nfcorpus | B | R1_BM25 | Relevant source not retrieved | 74 |
| nfcorpus | B | R1_BM25 | Relevant source ranked too low | 33 |
| nfcorpus | B | R1_BM25 | Relevant source retrieved but dropped by Evidence Selection | 41 |
| nfcorpus | B | R2_HYBRID_RRF | Relevant source not retrieved | 48 |
| nfcorpus | B | R2_HYBRID_RRF | Relevant source ranked too low | 37 |
| nfcorpus | B | R2_HYBRID_RRF | Relevant source retrieved but dropped by Evidence Selection | 40 |
| nfcorpus | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source not retrieved | 48 |
| nfcorpus | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source ranked too low | 37 |
| nfcorpus | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source retrieved but dropped by Evidence Selection | 39 |
| nfcorpus | B | R3_COVERAGE_RERANK | Relevant source not retrieved | 51 |
| nfcorpus | B | R3_COVERAGE_RERANK | Relevant source ranked too low | 39 |
| nfcorpus | B | R3_COVERAGE_RERANK | Relevant source retrieved but dropped by Evidence Selection | 42 |
| nfcorpus | B | R4_CROSS_ENCODER | Relevant source not retrieved | 51 |
| nfcorpus | B | R4_CROSS_ENCODER | Relevant source ranked too low | 42 |
| nfcorpus | B | R4_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 24 |
| nfcorpus | B | R5_HYBRID_CROSS_ENCODER | Relevant source not retrieved | 48 |
| nfcorpus | B | R5_HYBRID_CROSS_ENCODER | Relevant source ranked too low | 41 |
| nfcorpus | B | R5_HYBRID_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 30 |
| nfcorpus | B | R6_QUERY_REWRITING | Relevant source not retrieved | 24 |
| nfcorpus | B | R6_QUERY_REWRITING | Relevant source ranked too low | 8 |
| nfcorpus | B | R6_QUERY_REWRITING | Relevant source retrieved but dropped by Evidence Selection | 8 |
| nfcorpus | B | R7_MULTI_QUERY | Relevant source not retrieved | 21 |
| nfcorpus | B | R7_MULTI_QUERY | Relevant source ranked too low | 12 |
| nfcorpus | B | R7_MULTI_QUERY | Relevant source retrieved but dropped by Evidence Selection | 7 |
| nfcorpus | B | R8_HYDE | Query rewrite semantic drift | 1 |
| nfcorpus | B | R8_HYDE | Relevant source not retrieved | 18 |
| nfcorpus | B | R8_HYDE | Relevant source ranked too low | 11 |
| nfcorpus | B | R8_HYDE | Relevant source retrieved but dropped by Evidence Selection | 4 |
| scifact | A | B0_BASIC_DENSE_RAG | Relevant source not retrieved | 17 |
| scifact | A | B0_BASIC_DENSE_RAG | Relevant source ranked too low | 29 |
| scifact | A | B0_BASIC_DENSE_RAG | Relevant source retrieved but dropped by Evidence Selection | 35 |
| scifact | A | R1_BM25 | Relevant source not retrieved | 32 |
| scifact | A | R1_BM25 | Relevant source ranked too low | 26 |
| scifact | A | R1_BM25 | Relevant source retrieved but dropped by Evidence Selection | 32 |
| scifact | A | R2_HYBRID_RRF | Relevant source not retrieved | 10 |
| scifact | A | R2_HYBRID_RRF | Relevant source ranked too low | 39 |
| scifact | A | R2_HYBRID_RRF | Relevant source retrieved but dropped by Evidence Selection | 32 |
| scifact | A | R3_COVERAGE_RERANK | Relevant source not retrieved | 17 |
| scifact | A | R3_COVERAGE_RERANK | Relevant source ranked too low | 61 |
| scifact | A | R3_COVERAGE_RERANK | Relevant source retrieved but dropped by Evidence Selection | 30 |
| scifact | A | R4_CROSS_ENCODER | Relevant source not retrieved | 17 |
| scifact | A | R4_CROSS_ENCODER | Relevant source ranked too low | 33 |
| scifact | A | R4_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 34 |
| scifact | A | R5_HYBRID_CROSS_ENCODER | Relevant source not retrieved | 10 |
| scifact | A | R5_HYBRID_CROSS_ENCODER | Relevant source ranked too low | 42 |
| scifact | A | R5_HYBRID_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 31 |
| scifact | B | B0_BASIC_DENSE_RAG | Relevant source not retrieved | 16 |
| scifact | B | B0_BASIC_DENSE_RAG | Relevant source ranked too low | 29 |
| scifact | B | B0_BASIC_DENSE_RAG | Relevant source retrieved but dropped by Evidence Selection | 39 |
| scifact | B | O0_SECTION_AWARE_256_32 | Relevant source not retrieved | 16 |
| scifact | B | O0_SECTION_AWARE_256_32 | Relevant source ranked too low | 29 |
| scifact | B | O0_SECTION_AWARE_256_32 | Relevant source retrieved but dropped by Evidence Selection | 39 |
| scifact | B | O1_FIXED_256_32 | Relevant source not retrieved | 16 |
| scifact | B | O1_FIXED_256_32 | Relevant source ranked too low | 29 |
| scifact | B | O1_FIXED_256_32 | Relevant source retrieved but dropped by Evidence Selection | 39 |
| scifact | B | O2_NO_OVERLAP | Relevant source not retrieved | 16 |
| scifact | B | O2_NO_OVERLAP | Relevant source ranked too low | 36 |
| scifact | B | O2_NO_OVERLAP | Relevant source retrieved but dropped by Evidence Selection | 33 |
| scifact | B | O3_SMALL_CHUNKS | Relevant source not retrieved | 12 |
| scifact | B | O3_SMALL_CHUNKS | Relevant source ranked too low | 32 |
| scifact | B | O3_SMALL_CHUNKS | Relevant source retrieved but dropped by Evidence Selection | 40 |
| scifact | B | O4_LARGE_CHUNKS | Relevant source not retrieved | 16 |
| scifact | B | O4_LARGE_CHUNKS | Relevant source ranked too low | 30 |
| scifact | B | O4_LARGE_CHUNKS | Relevant source retrieved but dropped by Evidence Selection | 34 |
| scifact | B | O5_RECURSIVE | Relevant source not retrieved | 16 |
| scifact | B | O5_RECURSIVE | Relevant source ranked too low | 33 |
| scifact | B | O5_RECURSIVE | Relevant source retrieved but dropped by Evidence Selection | 36 |
| scifact | B | O6_ALTERNATIVE_EMBEDDING | Relevant source not retrieved | 20 |
| scifact | B | O6_ALTERNATIVE_EMBEDDING | Relevant source ranked too low | 35 |
| scifact | B | O6_ALTERNATIVE_EMBEDDING | Relevant source retrieved but dropped by Evidence Selection | 41 |
| scifact | B | O7_EXACT_SEARCH | Relevant source not retrieved | 16 |
| scifact | B | O7_EXACT_SEARCH | Relevant source ranked too low | 29 |
| scifact | B | O7_EXACT_SEARCH | Relevant source retrieved but dropped by Evidence Selection | 39 |
| scifact | B | O8_HNSW_ANN | Relevant source not retrieved | 16 |
| scifact | B | O8_HNSW_ANN | Relevant source ranked too low | 29 |
| scifact | B | O8_HNSW_ANN | Relevant source retrieved but dropped by Evidence Selection | 39 |
| scifact | B | R11_TOKEN_BUDGET_SELECTION | Relevant source not retrieved | 16 |
| scifact | B | R11_TOKEN_BUDGET_SELECTION | Relevant source ranked too low | 29 |
| scifact | B | R11_TOKEN_BUDGET_SELECTION | Relevant source retrieved but dropped by Evidence Selection | 9 |
| scifact | B | R12_SUFFICIENCY_GATE | Relevant source not retrieved | 16 |
| scifact | B | R12_SUFFICIENCY_GATE | Relevant source ranked too low | 29 |
| scifact | B | R12_SUFFICIENCY_GATE | Relevant source retrieved but dropped by Evidence Selection | 39 |
| scifact | B | R13_RANKGPT | Relevant source not retrieved | 7 |
| scifact | B | R13_RANKGPT | Relevant source ranked too low | 6 |
| scifact | B | R13_RANKGPT | Relevant source retrieved but dropped by Evidence Selection | 15 |
| scifact | B | R14_FULL_ADVANCED | Relevant source not retrieved | 4 |
| scifact | B | R14_FULL_ADVANCED | Relevant source ranked too low | 13 |
| scifact | B | R14_FULL_ADVANCED | Relevant source retrieved but dropped by Evidence Selection | 7 |
| scifact | B | R1_BM25 | Relevant source not retrieved | 36 |
| scifact | B | R1_BM25 | Relevant source ranked too low | 27 |
| scifact | B | R1_BM25 | Relevant source retrieved but dropped by Evidence Selection | 34 |
| scifact | B | R2_HYBRID_RRF | Relevant source not retrieved | 11 |
| scifact | B | R2_HYBRID_RRF | Relevant source ranked too low | 36 |
| scifact | B | R2_HYBRID_RRF | Relevant source retrieved but dropped by Evidence Selection | 37 |
| scifact | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source not retrieved | 10 |
| scifact | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source ranked too low | 37 |
| scifact | B | R2_HYBRID_RRF_MATCHED_BUDGET | Relevant source retrieved but dropped by Evidence Selection | 37 |
| scifact | B | R3_COVERAGE_RERANK | Relevant source not retrieved | 16 |
| scifact | B | R3_COVERAGE_RERANK | Relevant source ranked too low | 56 |
| scifact | B | R3_COVERAGE_RERANK | Relevant source retrieved but dropped by Evidence Selection | 32 |
| scifact | B | R4_CROSS_ENCODER | Relevant source not retrieved | 16 |
| scifact | B | R4_CROSS_ENCODER | Relevant source ranked too low | 35 |
| scifact | B | R4_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 33 |
| scifact | B | R5_HYBRID_CROSS_ENCODER | Relevant source not retrieved | 11 |
| scifact | B | R5_HYBRID_CROSS_ENCODER | Relevant source ranked too low | 43 |
| scifact | B | R5_HYBRID_CROSS_ENCODER | Relevant source retrieved but dropped by Evidence Selection | 29 |
| scifact | B | R6_QUERY_REWRITING | Relevant source not retrieved | 7 |
| scifact | B | R6_QUERY_REWRITING | Relevant source ranked too low | 8 |
| scifact | B | R6_QUERY_REWRITING | Relevant source retrieved but dropped by Evidence Selection | 15 |
| scifact | B | R7_MULTI_QUERY | Relevant source not retrieved | 8 |
| scifact | B | R7_MULTI_QUERY | Relevant source ranked too low | 8 |
| scifact | B | R7_MULTI_QUERY | Relevant source retrieved but dropped by Evidence Selection | 15 |
| scifact | B | R8_HYDE | Query rewrite semantic drift | 1 |
| scifact | B | R8_HYDE | Relevant source not retrieved | 7 |
| scifact | B | R8_HYDE | Relevant source ranked too low | 4 |
| scifact | B | R8_HYDE | Relevant source retrieved but dropped by Evidence Selection | 12 |

Per-query details: failure_analysis.csv (expected relevant IDs, retrieved IDs, selected IDs, change vs baseline).

## Limitations

- BEIR measures document ranking. No answer-quality metric is reported without annotated cases.
- Protocol B maps chunk rankings to documents by first appearance; it is not the BEIR leaderboard setting.
- LLM-based methods (R6, R7, R8, R13, R14) ran on a subset of queries; compare them with B0 on the same subset (paired columns).
- One auxiliary LLM was used for all LLM-based retrieval methods; results may differ with another model.
- No hyperparameter was tuned on the test splits: every value is the preset default declared before running.
- Gate and filter results come from a small author-written fixture, not from independent labels.
