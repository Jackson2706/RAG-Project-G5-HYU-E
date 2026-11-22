# dev-02: post-hoc analyses (EXPLORATORY, amendment A34)

Not pre-registered. From the per-case tables of evaluator v1 and v2 and A0's saved replies. Source: `scripts/posthoc_analyses.py`.

## Acceptable-action rate per expected behaviour

| evaluator | preset | answer (n) | abstain (n) | conditional_answer (n) | clarify (n) |
|---|---|---|---|---|---|
| v1 | A0_AAES | 0.190 (21) | 0.421 (19) | 0.800 (5) | 0.500 (2) |
| v1 | A1_AAES_HARD_FILTER | 0.190 (21) | 0.368 (19) | 0.800 (5) | 0.500 (2) |
| v1 | A2_AAES_ORACLE_PROFILE | 0.190 (21) | 0.316 (19) | 1.000 (5) | 0.500 (2) |
| v1 | A3_AAES_ALWAYS_CLARIFY | 0.190 (21) | 0.316 (19) | 0.800 (5) | 0.500 (2) |
| v1 | A4_QUESTION_ONLY_AMBIGUITY | 0.571 (21) | 0.684 (19) | 0.000 (5) | 0.000 (2) |
| v1 | A6_AAES_NO_TEMPORAL | 0.190 (21) | 0.421 (19) | 0.800 (5) | 0.500 (2) |
| v1 | B0_BASIC_DENSE_RAG | 0.857 (21) | 0.474 (19) | 0.000 (5) | 0.000 (2) |
| v1 | G0_CLOSED_BOOK | 1.000 (21) | 0.211 (19) | 0.000 (5) | 0.000 (2) |
| v1 | G1_ORACLE_CONTEXT | 0.905 (21) | 0.842 (19) | 0.000 (5) | 0.000 (2) |
| v1 | R15_SELF_QUERY | 0.952 (21) | 0.632 (19) | 0.000 (5) | 0.000 (2) |
| v1 | R16_PROMPTED_CONDITIONAL | 1.000 (21) | 0.526 (19) | 0.000 (5) | 0.000 (2) |
| v1 | R5_HYBRID_CROSS_ENCODER | 1.000 (21) | 0.579 (19) | 0.000 (5) | 0.000 (2) |
| v1 | R9S_SCOPE_PREFILTER | 1.000 (21) | 0.526 (19) | 0.000 (5) | 0.000 (2) |
| v2 | A0_AAES | 0.190 (21) | 0.421 (19) | 0.800 (5) | 0.500 (2) |
| v2 | A1_AAES_HARD_FILTER | 0.190 (21) | 0.368 (19) | 0.800 (5) | 0.500 (2) |
| v2 | A2_AAES_ORACLE_PROFILE | 0.190 (21) | 0.368 (19) | 1.000 (5) | 0.500 (2) |
| v2 | A3_AAES_ALWAYS_CLARIFY | 0.190 (21) | 0.316 (19) | 0.800 (5) | 0.500 (2) |
| v2 | A4_QUESTION_ONLY_AMBIGUITY | 0.571 (21) | 0.684 (19) | 0.000 (5) | 0.000 (2) |
| v2 | A6_AAES_NO_TEMPORAL | 0.190 (21) | 0.421 (19) | 0.800 (5) | 0.500 (2) |
| v2 | B0_BASIC_DENSE_RAG | 0.714 (21) | 0.842 (19) | 0.000 (5) | 0.000 (2) |
| v2 | G0_CLOSED_BOOK | 0.952 (21) | 0.421 (19) | 0.000 (5) | 0.000 (2) |
| v2 | G1_ORACLE_CONTEXT | 0.857 (21) | 0.895 (19) | 0.000 (5) | 0.000 (2) |
| v2 | R15_SELF_QUERY | 0.810 (21) | 0.789 (19) | 0.000 (5) | 0.000 (2) |
| v2 | R16_PROMPTED_CONDITIONAL | 0.762 (21) | 0.789 (19) | 0.000 (5) | 0.500 (2) |
| v2 | R5_HYBRID_CROSS_ENCODER | 0.857 (21) | 0.842 (19) | 0.000 (5) | 0.000 (2) |
| v2 | R9S_SCOPE_PREFILTER | 0.952 (21) | 0.737 (19) | 0.000 (5) | 0.000 (2) |

## Branch detection (positive = conditional_answer or clarify)

| evaluator | preset | TP | predicted | expected | precision | recall |
|---|---|---|---|---|---|---|
| v1 | A0_AAES | 5 | 29 | 7 | 0.172 | 0.714 |
| v1 | A1_AAES_HARD_FILTER | 5 | 30 | 7 | 0.167 | 0.714 |
| v1 | A2_AAES_ORACLE_PROFILE | 6 | 32 | 7 | 0.188 | 0.857 |
| v1 | A3_AAES_ALWAYS_CLARIFY | 5 | 32 | 7 | 0.156 | 0.714 |
| v1 | A4_QUESTION_ONLY_AMBIGUITY | 0 | 12 | 7 | 0.000 | 0.000 |
| v1 | A6_AAES_NO_TEMPORAL | 5 | 29 | 7 | 0.172 | 0.714 |
| v1 | B0_BASIC_DENSE_RAG | 0 | 0 | 7 | N/A | 0.000 |
| v1 | G0_CLOSED_BOOK | 0 | 0 | 7 | N/A | 0.000 |
| v1 | G1_ORACLE_CONTEXT | 0 | 0 | 7 | N/A | 0.000 |
| v1 | R15_SELF_QUERY | 0 | 0 | 7 | N/A | 0.000 |
| v1 | R16_PROMPTED_CONDITIONAL | 0 | 0 | 7 | N/A | 0.000 |
| v1 | R5_HYBRID_CROSS_ENCODER | 0 | 0 | 7 | N/A | 0.000 |
| v1 | R9S_SCOPE_PREFILTER | 0 | 0 | 7 | N/A | 0.000 |
| v2 | A0_AAES | 5 | 29 | 7 | 0.172 | 0.714 |
| v2 | A1_AAES_HARD_FILTER | 5 | 30 | 7 | 0.167 | 0.714 |
| v2 | A2_AAES_ORACLE_PROFILE | 6 | 31 | 7 | 0.194 | 0.857 |
| v2 | A3_AAES_ALWAYS_CLARIFY | 5 | 32 | 7 | 0.156 | 0.714 |
| v2 | A4_QUESTION_ONLY_AMBIGUITY | 0 | 12 | 7 | 0.000 | 0.000 |
| v2 | A6_AAES_NO_TEMPORAL | 5 | 29 | 7 | 0.172 | 0.714 |
| v2 | B0_BASIC_DENSE_RAG | 0 | 0 | 7 | N/A | 0.000 |
| v2 | G0_CLOSED_BOOK | 0 | 0 | 7 | N/A | 0.000 |
| v2 | G1_ORACLE_CONTEXT | 0 | 0 | 7 | N/A | 0.000 |
| v2 | R15_SELF_QUERY | 0 | 0 | 7 | N/A | 0.000 |
| v2 | R16_PROMPTED_CONDITIONAL | 1 | 4 | 7 | 0.250 | 0.143 |
| v2 | R5_HYBRID_CROSS_ENCODER | 0 | 0 | 7 | N/A | 0.000 |
| v2 | R9S_SCOPE_PREFILTER | 0 | 0 | 7 | N/A | 0.000 |

## A0 counts

| count | value |
|---|---|
| A0 CLARIFY | 21 |
| A0 CLARIFY asks for campus | 13 |
| A0 CLARIFY asks for academic status | 4 |
| A0 CLARIFY asks for degree level | 3 |
| A0 CLARIFY asks for visa | 1 |
| A0 CLARIFY on cases labelled abstain | 9 |
| cases labelled abstain | 19 |
| cases that need branching (labelled conditional_answer or clarify) | 7 |
| cases | 47 |
