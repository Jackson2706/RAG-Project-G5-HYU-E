**Limitation (state it in every report):** this is an automated audit. The reference annotator, Codex, also wrote the tagging rules, and the audit is not human-validated.

# Automated applicability tag audit

## G2

| Attribute | Occurrences | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| degree_level | 33 | 0.909 [0.764, 0.969] | 0.909 [0.804, 0.961] | 0.735 [0.620, 0.826] | 0.735 [0.620, 0.826] | 0.667 [0.554, 0.763] | 0.710 [0.599, 0.801] | PASS |
| year | 6 | 0.667 [0.300, 0.903] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 0.875 [0.640, 0.965] | 0.954 [0.738, 0.993] | PASS |
| visa | 9 | 0.667 [0.354, 0.879] | 0.857 [0.487, 0.974] | 0.667 [0.354, 0.879] | 0.667 [0.354, 0.879] | 0.500 [0.254, 0.746] | 0.599 [0.332, 0.817] | FAIL |
| topik_level | 17 | 1.000 [0.816, 1.000] | 0.925 [0.846, 0.965] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] | PASS |
| english_track | 5 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | PASS |
| academic_status | 57 | 0.895 [0.789, 0.951] | 1.000 [0.926, 1.000] | 0.923 [0.818, 0.970] | 0.923 [0.818, 0.970] | 0.828 [0.711, 0.904] | 0.888 [0.782, 0.946] | PASS |
| campus | 145 | 1.000 [0.974, 1.000] | 0.955 [0.909, 0.978] | 0.961 [0.917, 0.982] | 0.955 [0.910, 0.978] | 0.961 [0.917, 0.982] | 0.955 [0.910, 0.978] | PASS |
| scope | 150 | 1.000 [0.975, 1.000] | 0.933 [0.882, 0.963] | 0.933 [0.882, 0.963] | 0.942 [0.892, 0.969] | 0.933 [0.882, 0.963] | 0.942 [0.892, 0.969] | PASS |
| effective_term | 97 | 1.000 [0.962, 1.000] | 0.896 [0.819, 0.942] | 0.887 [0.808, 0.935] | 0.856 [0.773, 0.912] | 0.887 [0.808, 0.935] | 0.856 [0.773, 0.912] | PASS |

G2 verdict: **FAIL**.

## Unknown-condition estimate

Reference-conditioned unknown chunks: 13/63 (0.206 [0.125, 0.322]).
Estimated conditioned chunks among 387 index unknowns: 79.9 [48.3, 124.5].
Top attributes: academic_status (6), degree_level (3), visa (3), year (2).

## by method

### rule

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 33 | 50 | 5 | 18 | 0.909 [0.764, 0.969] | 0.909 [0.804, 0.961] | 0.735 [0.620, 0.826] | 0.735 [0.620, 0.826] | 0.667 [0.554, 0.763] | 0.710 [0.599, 0.801] |
| year | 6 | 14 | 0 | 0 | 0.667 [0.300, 0.903] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 0.875 [0.640, 0.965] | 0.954 [0.738, 0.993] |
| student_type | 2 | 2 | 0 | 0 | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] |
| visa | 9 | 6 | 1 | 3 | 0.667 [0.354, 0.879] | 0.857 [0.487, 0.974] | 0.667 [0.354, 0.879] | 0.667 [0.354, 0.879] | 0.500 [0.254, 0.746] | 0.599 [0.332, 0.817] |
| topik_level | 17 | 74 | 6 | 4 | 1.000 [0.816, 1.000] | 0.925 [0.846, 0.965] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] |
| english_track | 5 | 5 | 0 | 0 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] |
| academic_status | 57 | 48 | 0 | 4 | 0.895 [0.789, 0.951] | 1.000 [0.926, 1.000] | 0.923 [0.818, 0.970] | 0.923 [0.818, 0.970] | 0.828 [0.711, 0.904] | 0.888 [0.782, 0.946] |
| korean_standard | 1 | 0 | 0 | 1 | 1.000 [0.207, 1.000] | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 145 | 147 | 7 | 6 | 1.000 [0.974, 1.000] | 0.955 [0.909, 0.978] | 0.961 [0.917, 0.982] | 0.955 [0.910, 0.978] | 0.961 [0.917, 0.982] | 0.955 [0.910, 0.978] |
| scope | 150 | 140 | 10 | 10 | 1.000 [0.975, 1.000] | 0.933 [0.882, 0.963] | 0.933 [0.882, 0.963] | 0.942 [0.892, 0.969] | 0.933 [0.882, 0.963] | 0.942 [0.892, 0.969] |
| effective_term | 97 | 86 | 10 | 11 | 1.000 [0.962, 1.000] | 0.896 [0.819, 0.942] | 0.887 [0.808, 0.935] | 0.856 [0.773, 0.912] | 0.887 [0.808, 0.935] | 0.856 [0.773, 0.912] |

### llm

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| scope | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| effective_term | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |


## by bucket

### rule_tagged

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 30 | 50 | 5 | 18 | 1.000 [0.886, 1.000] | 0.909 [0.804, 0.961] | 0.735 [0.620, 0.826] | 0.735 [0.620, 0.826] | 0.735 [0.620, 0.826] | 0.735 [0.620, 0.826] |
| year | 4 | 14 | 0 | 0 | 1.000 [0.510, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] |
| student_type | 2 | 2 | 0 | 0 | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] |
| visa | 6 | 6 | 1 | 3 | 1.000 [0.610, 1.000] | 0.857 [0.487, 0.974] | 0.667 [0.354, 0.879] | 0.667 [0.354, 0.879] | 0.667 [0.354, 0.879] | 0.667 [0.354, 0.879] |
| topik_level | 17 | 74 | 6 | 4 | 1.000 [0.816, 1.000] | 0.925 [0.846, 0.965] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] |
| english_track | 5 | 5 | 0 | 0 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] |
| academic_status | 51 | 48 | 0 | 4 | 1.000 [0.930, 1.000] | 1.000 [0.926, 1.000] | 0.923 [0.818, 0.970] | 0.923 [0.818, 0.970] | 0.923 [0.818, 0.970] | 0.923 [0.818, 0.970] |
| korean_standard | 1 | 0 | 0 | 1 | 1.000 [0.207, 1.000] | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 63 | 62 | 2 | 4 | 1.000 [0.943, 1.000] | 0.969 [0.893, 0.991] | 0.939 [0.854, 0.976] | 0.939 [0.854, 0.976] | 0.939 [0.854, 0.976] | 0.939 [0.854, 0.976] |
| scope | 66 | 62 | 4 | 4 | 1.000 [0.945, 1.000] | 0.939 [0.854, 0.976] | 0.939 [0.854, 0.976] | 0.939 [0.854, 0.976] | 0.939 [0.854, 0.976] | 0.939 [0.854, 0.976] |
| effective_term | 55 | 45 | 10 | 10 | 1.000 [0.935, 1.000] | 0.818 [0.697, 0.898] | 0.818 [0.697, 0.898] | 0.818 [0.697, 0.898] | 0.818 [0.697, 0.898] | 0.818 [0.697, 0.898] |

### rule_unconditioned

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 21 | 22 | 0 | 0 | 1.000 [0.845, 1.000] | 1.000 [0.851, 1.000] | 1.000 [0.851, 1.000] | 1.000 [0.851, 1.000] | 1.000 [0.851, 1.000] | 1.000 [0.851, 1.000] |
| scope | 21 | 21 | 0 | 0 | 1.000 [0.845, 1.000] | 1.000 [0.845, 1.000] | 1.000 [0.845, 1.000] | 1.000 [0.845, 1.000] | 1.000 [0.845, 1.000] | 1.000 [0.845, 1.000] |
| effective_term | 6 | 6 | 0 | 0 | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] |

### rule_cue_unknown

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 3 | 0 | 0 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.354] | 0.000 [0.000, 0.354] |
| year | 2 | 0 | 0 | 0 | 0.000 [0.000, 0.658] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.658] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 3 | 0 | 0 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.562] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 6 | 0 | 0 | 0 | 0.000 [0.000, 0.390] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.390] | 0.000 [0.000, 0.390] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 61 | 63 | 5 | 2 | 1.000 [0.941, 1.000] | 0.926 [0.839, 0.968] | 0.969 [0.895, 0.992] | 0.969 [0.895, 0.992] | 0.969 [0.895, 0.992] | 0.969 [0.895, 0.992] |
| scope | 63 | 57 | 6 | 6 | 1.000 [0.943, 1.000] | 0.905 [0.807, 0.956] | 0.905 [0.807, 0.956] | 0.905 [0.807, 0.956] | 0.905 [0.807, 0.956] | 0.905 [0.807, 0.956] |
| effective_term | 36 | 35 | 0 | 1 | 1.000 [0.904, 1.000] | 1.000 [0.901, 1.000] | 0.972 [0.858, 0.995] | 0.972 [0.858, 0.995] | 0.972 [0.858, 0.995] | 0.972 [0.858, 0.995] |

### llm_tagged

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| scope | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| effective_term | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |

### llm_unconditioned

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| scope | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| effective_term | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |

### llm_rejected

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| scope | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| effective_term | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |

### llm_errors

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| scope | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| effective_term | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |


## by campus

### seoul

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 24 | 32 | 5 | 13 | 0.875 [0.690, 0.957] | 0.865 [0.720, 0.941] | 0.711 [0.566, 0.823] | 0.711 [0.566, 0.823] | 0.615 [0.480, 0.735] | 0.675 [0.540, 0.787] |
| year | 4 | 6 | 0 | 0 | 0.500 [0.150, 0.850] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 0.750 [0.409, 0.929] | 0.898 [0.553, 0.984] |
| student_type | 1 | 1 | 0 | 0 | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| visa | 5 | 2 | 0 | 1 | 0.400 [0.118, 0.769] | 1.000 [0.342, 1.000] | 0.667 [0.208, 0.939] | 0.667 [0.208, 0.939] | 0.333 [0.097, 0.700] | 0.497 [0.186, 0.811] |
| topik_level | 15 | 67 | 0 | 0 | 1.000 [0.796, 1.000] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] |
| english_track | 4 | 4 | 0 | 0 | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] |
| academic_status | 42 | 34 | 0 | 4 | 0.881 [0.750, 0.948] | 1.000 [0.898, 1.000] | 0.895 [0.759, 0.958] | 0.895 [0.759, 0.958] | 0.791 [0.648, 0.886] | 0.856 [0.722, 0.932] |
| korean_standard | 1 | 0 | 0 | 1 | 1.000 [0.207, 1.000] | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 91 | 90 | 6 | 4 | 1.000 [0.959, 1.000] | 0.938 [0.870, 0.971] | 0.957 [0.896, 0.983] | 0.959 [0.898, 0.984] | 0.957 [0.896, 0.983] | 0.959 [0.898, 0.984] |
| scope | 94 | 87 | 7 | 7 | 1.000 [0.961, 1.000] | 0.926 [0.854, 0.963] | 0.926 [0.854, 0.963] | 0.944 [0.878, 0.975] | 0.926 [0.854, 0.963] | 0.944 [0.878, 0.975] |
| effective_term | 79 | 77 | 2 | 2 | 1.000 [0.954, 1.000] | 0.975 [0.912, 0.993] | 0.975 [0.912, 0.993] | 0.965 [0.898, 0.988] | 0.975 [0.912, 0.993] | 0.965 [0.898, 0.988] |

### erica

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 9 | 18 | 0 | 5 | 1.000 [0.701, 1.000] | 1.000 [0.824, 1.000] | 0.783 [0.581, 0.903] | 0.783 [0.581, 0.903] | 0.783 [0.581, 0.903] | 0.783 [0.581, 0.903] |
| year | 2 | 8 | 0 | 0 | 1.000 [0.342, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] |
| student_type | 1 | 1 | 0 | 0 | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| visa | 4 | 4 | 1 | 2 | 1.000 [0.510, 1.000] | 0.800 [0.376, 0.964] | 0.667 [0.300, 0.903] | 0.667 [0.300, 0.903] | 0.667 [0.300, 0.903] | 0.667 [0.300, 0.903] |
| topik_level | 2 | 7 | 6 | 4 | 1.000 [0.342, 1.000] | 0.538 [0.291, 0.768] | 0.636 [0.354, 0.848] | 0.636 [0.354, 0.848] | 0.636 [0.354, 0.848] | 0.636 [0.354, 0.848] |
| english_track | 1 | 1 | 0 | 0 | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| academic_status | 15 | 14 | 0 | 0 | 0.933 [0.702, 0.988] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 0.933 [0.702, 0.988] | 0.976 [0.760, 0.998] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 54 | 57 | 1 | 2 | 1.000 [0.934, 1.000] | 0.983 [0.909, 0.997] | 0.966 [0.885, 0.991] | 0.950 [0.862, 0.983] | 0.966 [0.885, 0.991] | 0.950 [0.862, 0.983] |
| scope | 56 | 53 | 3 | 3 | 1.000 [0.936, 1.000] | 0.946 [0.854, 0.982] | 0.946 [0.854, 0.982] | 0.937 [0.841, 0.977] | 0.946 [0.854, 0.982] | 0.937 [0.841, 0.977] |
| effective_term | 18 | 9 | 8 | 9 | 1.000 [0.824, 1.000] | 0.529 [0.310, 0.738] | 0.500 [0.290, 0.710] | 0.449 [0.249, 0.667] | 0.500 [0.290, 0.710] | 0.449 [0.249, 0.667] |

## `any_of` exact match

All chunks: 148/150 (0.9866666666666667).
Chunks with `any_of` on either side: 4/6 (0.6666666666666666).

## Disagreement review

Predicted side: 21; reference side: 69; both wrong: 3; ambiguous: 7.
Carried decisions: 83.

## Out-of-vocabulary conditions

| Text | Count |
|---|---:|
| recommendation letter from a Hanyang advisory professor | 4 |
| undergraduate GPA at least 3.0 or graduate GPA at least 4.2; outside scholarships that prohibit double benefits; valid certificate by deadline; IELTS/TOEFL score requirement | 3 |
| TOPIK transcripts, test history, Korean bank-account copy, and application form | 2 |
| foreign nationality and legal eligibility to work in Korea, including registered foreigners or overseas Koreans | 2 |
| interview if necessary | 2 |
| valid ID required for card pick-up | 2 |
| English communication, basic Korean communication, and mechanical-engineering major | 1 |
| English-test scores, thesis qualification, comprehensive examination, and off-campus residence prohibition | 1 |
| English-track students must meet one of the listed TOEFL, IELTS, CEFR, or TEPS scores; alternatives to TOPIK include KIIP or King Sejong Institute thresholds | 1 |
| GPA of 3.5 or higher and specified admission route for the four-year scholarship | 1 |
| Indian or Middle Eastern nationality, ability to start work in July 2022, and bilingual English and Korean; preference: chemical engineering | 1 |
| Indonesian nationality, age 19–34, residence in Korea, and interest in entrepreneurship and Indonesian environmental or energy issues | 1 |
| Indonesian nationality, age 19–34, residence in Korea, and interest in entrepreneurship and Indonesian environmental, energy, or local issues | 1 |
| TOPIK score must improve over the previously submitted score; expected graduates, leave students, extra-semester students, completed students, and prior Level 6 submitters excluded; criteria differ for arts and non-arts programs | 1 |
| Vietnamese nationality, ability to work in Korea and Vietnam, passport and ARC, academic and graduation records; preference: software-related major and Korean or English ability | 1 |

## Audience

| Value | Count |
|---|---:|
| applicant | 34 |
| admitted | 5 |
| enrolled | 60 |

## TOPIK scope

| Value | Count |
|---|---:|
| whole_chunk | 17 |
| one_line | 5 |
| null | 128 |
