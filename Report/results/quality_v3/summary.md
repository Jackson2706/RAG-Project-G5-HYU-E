# Evaluator v3: answer quality of saved replies (post hoc, LLM judge, A36)

Judge: fresh `claude-code:claude-opus-5-5` subagents, blind to preset names, items shuffled; prompt `Sources/evaluation/judge_v3_prompt.md` (frozen before any test item was judged). Not pre-registered as an evaluator: it computes the pre-registered correctness comparison post hoc.

## test-1 (121 cases)

| Preset | fact coverage | answered (answer cases) | coverage when answered | wrong-fact rate | wrong-group rate | answered replies (wrong-group base) | citation support | correct conditions (branching) | useful question | right referral | right referral (per abstain case) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B0_BASIC_DENSE_RAG | 0.300 | 0.633 | 0.474 | 0.117 | 0.265 | 68.000 | 0.573 | 0.000 | n/a | 0.340 | 0.283 |
| R15_SELF_QUERY | 0.269 | 0.617 | 0.437 | 0.133 | 0.194 | 67.000 | 0.561 | 0.000 | n/a | 0.333 | 0.217 |
| R16_PROMPTED_CONDITIONAL | 0.258 | 0.700 | 0.369 | 0.133 | 0.224 | 76.000 | 0.520 | 0.000 | n/a | 0.267 | 0.174 |
| A0_AAES | 0.119 | 0.417 | 0.287 | 0.067 | 0.125 | 40.000 | 0.506 | 0.267 | 0.096 | 0.724 | 0.174 |
| G0_CLOSED_BOOK | 0.079 | 0.767 | 0.103 | 0.383 | 0.200 | 90.000 | n/a | 0.000 | n/a | 0.742 | 0.283 |
| G1_ORACLE_CONTEXT | 0.463 | 0.717 | 0.645 | 0.033 | 0.076 | 66.000 | 0.880 | 0.000 | n/a | 0.491 | 0.435 |

## dev (47 cases, validation)

| Preset | fact coverage | answered (answer cases) | coverage when answered | wrong-fact rate | wrong-group rate | answered replies (wrong-group base) | citation support | correct conditions (branching) | useful question | right referral | right referral (per abstain case) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B0_BASIC_DENSE_RAG | 0.278 | 0.714 | 0.389 | 0.048 | 0.296 | 27.000 | 0.815 | 0.000 | n/a | 0.250 | 0.211 |
| R15_SELF_QUERY | 0.389 | 0.810 | 0.480 | 0.095 | 0.154 | 26.000 | 0.740 | 0.000 | n/a | 0.333 | 0.263 |
| R16_PROMPTED_CONDITIONAL | 0.325 | 0.857 | 0.380 | 0.286 | 0.259 | 27.000 | 0.676 | 0.000 | n/a | 0.300 | 0.263 |
| A0_AAES | 0.151 | 0.429 | 0.352 | 0.143 | 0.154 | 13.000 | 0.667 | 0.429 | 0.143 | 0.923 | 0.368 |
| G0_CLOSED_BOOK | 0.151 | 0.952 | 0.158 | 0.619 | 0.098 | 41.000 | n/a | 0.000 | n/a | 0.667 | 0.211 |
| G1_ORACLE_CONTEXT | 0.516 | 0.857 | 0.602 | 0.048 | 0.120 | 25.000 | 0.860 | 0.000 | n/a | 0.636 | 0.632 |

## Paired comparisons on test-1 (bootstrap 95% CI, permutation p; post hoc, not Holm-corrected)

| Comparison | Metric | diff | 95% CI | p |
|---|---|---|---|---|
| A0 vs B0 | fact coverage | -0.181 | [-0.281, -0.085] | 0.0008 |
| A0 vs B0 | answered (answer cases) | -0.217 | [-0.367, -0.061] | 0.0140 |
| A0 vs B0 | coverage when answered | -0.187 | [-0.352, -0.022] | 0.0371 |
| A0 vs B0 | wrong-fact rate | -0.050 | [-0.138, +0.034] | 0.4555 |
| A0 vs B0 | wrong-group rate | -0.140 | [-0.280, +0.001] | 0.0621 |
| A0 vs B0 | citation support | -0.067 | [-0.240, +0.108] | 0.5366 |
| A0 vs B0 | correct conditions (branching) | +0.267 | [+0.059, +0.500] | 0.1208 |
| A0 vs B0 | right referral | +0.385 | [+0.174, +0.586] | 0.0006 |
| A0 vs B0 | right referral (per abstain case) | -0.109 | [-0.250, +0.025] | 0.2332 |
| A0 vs R16 | fact coverage | -0.139 | [-0.227, -0.057] | 0.0028 |
| A0 vs R16 | answered (answer cases) | -0.283 | [-0.444, -0.121] | 0.0024 |
| A0 vs R16 | coverage when answered | -0.082 | [-0.236, +0.068] | 0.2931 |
| A0 vs R16 | wrong-fact rate | -0.067 | [-0.169, +0.035] | 0.3476 |
| A0 vs R16 | wrong-group rate | -0.099 | [-0.240, +0.046] | 0.1790 |
| A0 vs R16 | citation support | -0.013 | [-0.165, +0.144] | 0.8758 |
| A0 vs R16 | correct conditions (branching) | +0.267 | [+0.059, +0.500] | 0.1208 |
| A0 vs R16 | right referral | +0.457 | [+0.244, +0.657] | 0.0002 |
| A0 vs R16 | right referral (per abstain case) | +0.000 | [-0.135, +0.136] | 1.0000 |
| PREREG 2: A0 vs R15, unconditional (non-inferiority -0.03: not met) | fact coverage | -0.185 | [-0.312, -0.065] | 0.0065 |

## Validation on dev

Second judge (claude-code:claude-sonnet-5-5, 100 dev items, blind to the first):

| Field | kappa | agreement | pairs |
|---|---|---|---|
| facts (per fact) | 0.859 | 0.915 | 130 |
| wrong_group | 0.854 | 0.964 | 55 |
| all cited sentences supported | 0.656 | 0.829 | 41 |
| right_referral | 0.791 | 0.900 | 30 |
| asks_branch_attribute | 1.000 | 1.000 | 15 |
| conditions_match | 1.000 | 1.000 | 10 |

Human check: `Report/notes/quality_human_check.csv` not filled in yet.
