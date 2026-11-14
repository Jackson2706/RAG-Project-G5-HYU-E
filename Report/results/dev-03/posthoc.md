# dev-03: post-hoc analyses (EXPLORATORY, amendment A34)

Not pre-registered. From the per-case tables of evaluator v1 and v2 and A0's saved replies. Source: `scripts/posthoc_analyses.py`.

## Acceptable-action rate per expected behaviour

| evaluator | preset | answer (n) | abstain (n) | conditional_answer (n) | clarify (n) |
|---|---|---|---|---|---|
| v1 | A0_AAES | 0.190 (21) | 0.421 (19) | 0.800 (5) | 0.500 (2) |
| v1 | A0b_AAES_SPEC_FIXED | 0.524 (21) | 0.842 (19) | 0.000 (5) | 0.000 (2) |
| v1 | B0_BASIC_DENSE_RAG | 0.857 (21) | 0.474 (19) | 0.000 (5) | 0.000 (2) |
| v1 | R16_PROMPTED_CONDITIONAL | 1.000 (21) | 0.579 (19) | 0.000 (5) | 0.000 (2) |
| v2 | A0_AAES | 0.190 (21) | 0.421 (19) | 0.800 (5) | 0.500 (2) |
| v2 | A0b_AAES_SPEC_FIXED | 0.524 (21) | 0.895 (19) | 0.000 (5) | 0.000 (2) |
| v2 | B0_BASIC_DENSE_RAG | 0.667 (21) | 0.842 (19) | 0.000 (5) | 0.000 (2) |
| v2 | R16_PROMPTED_CONDITIONAL | 0.762 (21) | 0.789 (19) | 0.000 (5) | 0.500 (2) |

## Branch detection (positive = conditional_answer or clarify)

| evaluator | preset | TP | predicted | expected | precision | recall |
|---|---|---|---|---|---|---|
| v1 | A0_AAES | 5 | 29 | 7 | 0.172 | 0.714 |
| v1 | A0b_AAES_SPEC_FIXED | 0 | 7 | 7 | 0.000 | 0.000 |
| v1 | B0_BASIC_DENSE_RAG | 0 | 0 | 7 | N/A | 0.000 |
| v1 | R16_PROMPTED_CONDITIONAL | 0 | 0 | 7 | N/A | 0.000 |
| v2 | A0_AAES | 5 | 29 | 7 | 0.172 | 0.714 |
| v2 | A0b_AAES_SPEC_FIXED | 0 | 6 | 7 | 0.000 | 0.000 |
| v2 | B0_BASIC_DENSE_RAG | 0 | 0 | 7 | N/A | 0.000 |
| v2 | R16_PROMPTED_CONDITIONAL | 1 | 4 | 7 | 0.250 | 0.143 |

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
