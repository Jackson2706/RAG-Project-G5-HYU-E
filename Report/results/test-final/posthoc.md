# test-final: post-hoc analyses (EXPLORATORY, amendment A34)

Not pre-registered. From the per-case tables of evaluator v1 and v2 and A0's saved replies. Source: `scripts/posthoc_analyses.py`.

## Acceptable-action rate per expected behaviour

| evaluator | preset | answer (n) | abstain (n) | conditional_answer (n) | clarify (n) |
|---|---|---|---|---|---|
| v1 | A0_AAES | 0.150 (60) | 0.239 (46) | 0.556 (9) | 0.833 (6) |
| v1 | A1_AAES_HARD_FILTER | 0.150 (60) | 0.217 (46) | 0.556 (9) | 0.833 (6) |
| v1 | A2_AAES_ORACLE_PROFILE | 0.150 (60) | 0.239 (46) | 0.556 (9) | 0.833 (6) |
| v1 | A3_AAES_ALWAYS_CLARIFY | 0.133 (60) | 0.239 (46) | 0.667 (9) | 0.833 (6) |
| v1 | A4_QUESTION_ONLY_AMBIGUITY | 0.550 (60) | 0.565 (46) | 0.111 (9) | 0.000 (6) |
| v1 | A6_AAES_NO_TEMPORAL | 0.150 (60) | 0.239 (46) | 0.556 (9) | 0.833 (6) |
| v1 | B0_BASIC_DENSE_RAG | 0.933 (60) | 0.717 (46) | 0.000 (9) | 0.000 (6) |
| v1 | G0_CLOSED_BOOK | 1.000 (60) | 0.435 (46) | 0.000 (9) | 0.000 (6) |
| v1 | G1_ORACLE_CONTEXT | 0.933 (60) | 0.935 (46) | 0.000 (9) | 0.000 (6) |
| v1 | R15_SELF_QUERY | 0.900 (60) | 0.696 (46) | 0.000 (9) | 0.000 (6) |
| v1 | R16_PROMPTED_CONDITIONAL | 0.917 (60) | 0.630 (46) | 0.000 (9) | 0.000 (6) |
| v1 | R5_HYBRID_CROSS_ENCODER | 0.850 (60) | 0.652 (46) | 0.000 (9) | 0.000 (6) |
| v1 | R9S_SCOPE_PREFILTER | 0.883 (60) | 0.652 (46) | 0.000 (9) | 0.000 (6) |
| v2 | A0_AAES | 0.167 (60) | 0.239 (46) | 0.556 (9) | 0.833 (6) |
| v2 | A1_AAES_HARD_FILTER | 0.183 (60) | 0.217 (46) | 0.556 (9) | 0.833 (6) |
| v2 | A2_AAES_ORACLE_PROFILE | 0.183 (60) | 0.261 (46) | 0.556 (9) | 0.833 (6) |
| v2 | A3_AAES_ALWAYS_CLARIFY | 0.117 (60) | 0.239 (46) | 0.667 (9) | 0.833 (6) |
| v2 | A4_QUESTION_ONLY_AMBIGUITY | 0.433 (60) | 0.652 (46) | 0.111 (9) | 0.000 (6) |
| v2 | A6_AAES_NO_TEMPORAL | 0.183 (60) | 0.239 (46) | 0.556 (9) | 0.833 (6) |
| v2 | B0_BASIC_DENSE_RAG | 0.667 (60) | 0.870 (46) | 0.000 (9) | 0.000 (6) |
| v2 | G0_CLOSED_BOOK | 0.767 (60) | 0.739 (46) | 0.111 (9) | 0.000 (6) |
| v2 | G1_ORACLE_CONTEXT | 0.733 (60) | 0.935 (46) | 0.000 (9) | 0.000 (6) |
| v2 | R15_SELF_QUERY | 0.650 (60) | 0.891 (46) | 0.000 (9) | 0.000 (6) |
| v2 | R16_PROMPTED_CONDITIONAL | 0.617 (60) | 0.804 (46) | 0.222 (9) | 0.000 (6) |
| v2 | R5_HYBRID_CROSS_ENCODER | 0.650 (60) | 0.870 (46) | 0.000 (9) | 0.000 (6) |
| v2 | R9S_SCOPE_PREFILTER | 0.650 (60) | 0.870 (46) | 0.000 (9) | 0.000 (6) |

## Branch detection (positive = conditional_answer or clarify)

| evaluator | preset | TP | predicted | expected | precision | recall |
|---|---|---|---|---|---|---|
| v1 | A0_AAES | 10 | 84 | 15 | 0.119 | 0.667 |
| v1 | A1_AAES_HARD_FILTER | 10 | 87 | 15 | 0.115 | 0.667 |
| v1 | A2_AAES_ORACLE_PROFILE | 10 | 81 | 15 | 0.123 | 0.667 |
| v1 | A3_AAES_ALWAYS_CLARIFY | 11 | 86 | 15 | 0.128 | 0.733 |
| v1 | A4_QUESTION_ONLY_AMBIGUITY | 1 | 26 | 15 | 0.038 | 0.067 |
| v1 | A6_AAES_NO_TEMPORAL | 10 | 84 | 15 | 0.119 | 0.667 |
| v1 | B0_BASIC_DENSE_RAG | 0 | 0 | 15 | N/A | 0.000 |
| v1 | G0_CLOSED_BOOK | 0 | 0 | 15 | N/A | 0.000 |
| v1 | G1_ORACLE_CONTEXT | 0 | 0 | 15 | N/A | 0.000 |
| v1 | R15_SELF_QUERY | 0 | 0 | 15 | N/A | 0.000 |
| v1 | R16_PROMPTED_CONDITIONAL | 0 | 0 | 15 | N/A | 0.000 |
| v1 | R5_HYBRID_CROSS_ENCODER | 0 | 0 | 15 | N/A | 0.000 |
| v1 | R9S_SCOPE_PREFILTER | 0 | 0 | 15 | N/A | 0.000 |
| v2 | A0_AAES | 10 | 81 | 15 | 0.123 | 0.667 |
| v2 | A1_AAES_HARD_FILTER | 10 | 83 | 15 | 0.120 | 0.667 |
| v2 | A2_AAES_ORACLE_PROFILE | 10 | 76 | 15 | 0.132 | 0.667 |
| v2 | A3_AAES_ALWAYS_CLARIFY | 11 | 86 | 15 | 0.128 | 0.733 |
| v2 | A4_QUESTION_ONLY_AMBIGUITY | 1 | 26 | 15 | 0.038 | 0.067 |
| v2 | A6_AAES_NO_TEMPORAL | 10 | 80 | 15 | 0.125 | 0.667 |
| v2 | B0_BASIC_DENSE_RAG | 0 | 1 | 15 | 0.000 | 0.000 |
| v2 | G0_CLOSED_BOOK | 1 | 2 | 15 | 0.500 | 0.067 |
| v2 | G1_ORACLE_CONTEXT | 0 | 0 | 15 | N/A | 0.000 |
| v2 | R15_SELF_QUERY | 0 | 0 | 15 | N/A | 0.000 |
| v2 | R16_PROMPTED_CONDITIONAL | 2 | 10 | 15 | 0.200 | 0.133 |
| v2 | R5_HYBRID_CROSS_ENCODER | 0 | 0 | 15 | N/A | 0.000 |
| v2 | R9S_SCOPE_PREFILTER | 0 | 0 | 15 | N/A | 0.000 |

## A0 counts

| count | value |
|---|---|
| A0 CLARIFY | 52 |
| A0 CLARIFY asks for campus | 35 |
| A0 CLARIFY asks for degree level | 7 |
| A0 CLARIFY asks for academic status | 5 |
| A0 CLARIFY asks for student type | 3 |
| A0 CLARIFY asks for TOPIK level | 2 |
| A0 CLARIFY on cases labelled abstain | 27 |
| cases labelled abstain | 46 |
| cases that need branching (labelled conditional_answer or clarify) | 15 |
| cases | 121 |
