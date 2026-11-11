**Limitation (state it in every report):** this is an automated audit. The reference annotator, Codex, also wrote the tagging rules, and the audit is not human-validated.

# Automated applicability tag audit

## G2

| Attribute | Occurrences | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| degree_level | 40 | 1.000 [0.912, 1.000] | 0.907 [0.801, 0.960] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] | FAIL |
| year | 5 | 1.000 [0.566, 1.000] | 1.000 [0.772, 1.000] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] | PASS |
| student_type | 6 | 1.000 [0.610, 1.000] | 1.000 [0.566, 1.000] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] | FAIL |
| visa | 8 | 1.000 [0.676, 1.000] | 0.750 [0.468, 0.911] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] | FAIL |
| topik_level | 13 | 1.000 [0.772, 1.000] | 1.000 [0.918, 1.000] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | PASS |
| academic_status | 40 | 0.925 [0.801, 0.974] | 0.973 [0.862, 0.995] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] | 0.857 [0.722, 0.933] | 0.884 [0.754, 0.950] | PASS |
| campus | 99 | 1.000 [0.963, 1.000] | 0.971 [0.919, 0.990] | 0.944 [0.884, 0.974] | 0.950 [0.891, 0.978] | 0.944 [0.884, 0.974] | 0.950 [0.891, 0.978] | PASS |
| scope | 100 | 1.000 [0.963, 1.000] | 0.960 [0.902, 0.984] | 0.960 [0.902, 0.984] | 0.960 [0.901, 0.984] | 0.960 [0.902, 0.984] | 0.960 [0.901, 0.984] | PASS |
| effective_term | 66 | 1.000 [0.945, 1.000] | 0.924 [0.835, 0.967] | 0.924 [0.835, 0.967] | 0.913 [0.821, 0.960] | 0.924 [0.835, 0.967] | 0.913 [0.821, 0.960] | PASS |

G2 verdict: **FAIL**.

## Unknown-condition estimate

Reference-conditioned unknown chunks: 3/30 (0.100 [0.035, 0.256]).
Estimated conditioned chunks among 387 index unknowns: 38.7 [13.4, 99.2].
Top attributes: academic_status (3).

## by method

### rule

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 40 | 49 | 5 | 43 | 1.000 [0.912, 1.000] | 0.907 [0.801, 0.960] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] |
| year | 5 | 13 | 0 | 2 | 1.000 [0.566, 1.000] | 1.000 [0.772, 1.000] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] |
| student_type | 6 | 5 | 0 | 4 | 1.000 [0.610, 1.000] | 1.000 [0.566, 1.000] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] |
| visa | 8 | 9 | 3 | 0 | 1.000 [0.676, 1.000] | 0.750 [0.468, 0.911] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] |
| topik_level | 13 | 43 | 0 | 10 | 1.000 [0.772, 1.000] | 1.000 [0.918, 1.000] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] |
| english_track | 3 | 3 | 0 | 0 | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] |
| academic_status | 40 | 36 | 1 | 3 | 0.925 [0.801, 0.974] | 0.973 [0.862, 0.995] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] | 0.857 [0.722, 0.933] | 0.884 [0.754, 0.950] |
| korean_standard | 3 | 0 | 0 | 4 | 1.000 [0.438, 1.000] | null [null] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] |
| campus | 99 | 102 | 3 | 6 | 1.000 [0.963, 1.000] | 0.971 [0.919, 0.990] | 0.944 [0.884, 0.974] | 0.950 [0.891, 0.978] | 0.944 [0.884, 0.974] | 0.950 [0.891, 0.978] |
| scope | 100 | 96 | 4 | 4 | 1.000 [0.963, 1.000] | 0.960 [0.902, 0.984] | 0.960 [0.902, 0.984] | 0.960 [0.901, 0.984] | 0.960 [0.902, 0.984] | 0.960 [0.901, 0.984] |
| effective_term | 66 | 61 | 5 | 5 | 1.000 [0.945, 1.000] | 0.924 [0.835, 0.967] | 0.924 [0.835, 0.967] | 0.913 [0.821, 0.960] | 0.924 [0.835, 0.967] | 0.913 [0.821, 0.960] |

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
| degree_level | 40 | 49 | 5 | 43 | 1.000 [0.912, 1.000] | 0.907 [0.801, 0.960] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] | 0.533 [0.431, 0.631] |
| year | 5 | 13 | 0 | 2 | 1.000 [0.566, 1.000] | 1.000 [0.772, 1.000] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] | 0.867 [0.621, 0.963] |
| student_type | 6 | 5 | 0 | 4 | 1.000 [0.610, 1.000] | 1.000 [0.566, 1.000] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] | 0.556 [0.267, 0.811] |
| visa | 8 | 9 | 3 | 0 | 1.000 [0.676, 1.000] | 0.750 [0.468, 0.911] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] | 1.000 [0.701, 1.000] |
| topik_level | 13 | 43 | 0 | 10 | 1.000 [0.772, 1.000] | 1.000 [0.918, 1.000] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] |
| english_track | 3 | 3 | 0 | 0 | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] |
| academic_status | 37 | 36 | 1 | 3 | 1.000 [0.906, 1.000] | 0.973 [0.862, 0.995] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] |
| korean_standard | 3 | 0 | 0 | 4 | 1.000 [0.438, 1.000] | null [null] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] |
| campus | 52 | 55 | 1 | 2 | 1.000 [0.931, 1.000] | 0.982 [0.906, 0.997] | 0.965 [0.881, 0.990] | 0.965 [0.881, 0.990] | 0.965 [0.881, 0.990] | 0.965 [0.881, 0.990] |
| scope | 53 | 51 | 2 | 2 | 1.000 [0.932, 1.000] | 0.962 [0.872, 0.990] | 0.962 [0.872, 0.990] | 0.962 [0.872, 0.990] | 0.962 [0.872, 0.990] | 0.962 [0.872, 0.990] |
| effective_term | 44 | 39 | 5 | 5 | 1.000 [0.920, 1.000] | 0.886 [0.760, 0.950] | 0.886 [0.760, 0.950] | 0.886 [0.760, 0.950] | 0.886 [0.760, 0.950] | 0.886 [0.760, 0.950] |

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
| campus | 17 | 17 | 0 | 1 | 1.000 [0.816, 1.000] | 1.000 [0.816, 1.000] | 0.944 [0.742, 0.990] | 0.944 [0.742, 0.990] | 0.944 [0.742, 0.990] | 0.944 [0.742, 0.990] |
| scope | 17 | 16 | 1 | 1 | 1.000 [0.816, 1.000] | 0.941 [0.730, 0.990] | 0.941 [0.730, 0.990] | 0.941 [0.730, 0.990] | 0.941 [0.730, 0.990] | 0.941 [0.730, 0.990] |
| effective_term | 6 | 6 | 0 | 0 | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] |

### rule_cue_unknown

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 3 | 0 | 0 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.562] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 30 | 30 | 2 | 3 | 1.000 [0.886, 1.000] | 0.938 [0.799, 0.983] | 0.909 [0.764, 0.969] | 0.909 [0.764, 0.969] | 0.909 [0.764, 0.969] | 0.909 [0.764, 0.969] |
| scope | 30 | 29 | 1 | 1 | 1.000 [0.886, 1.000] | 0.967 [0.833, 0.994] | 0.967 [0.833, 0.994] | 0.967 [0.833, 0.994] | 0.967 [0.833, 0.994] | 0.967 [0.833, 0.994] |
| effective_term | 16 | 16 | 0 | 0 | 1.000 [0.806, 1.000] | 1.000 [0.806, 1.000] | 1.000 [0.806, 1.000] | 1.000 [0.806, 1.000] | 1.000 [0.806, 1.000] | 1.000 [0.806, 1.000] |

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
| degree_level | 32 | 34 | 3 | 39 | 1.000 [0.893, 1.000] | 0.919 [0.787, 0.972] | 0.466 [0.356, 0.579] | 0.466 [0.356, 0.579] | 0.466 [0.356, 0.579] | 0.466 [0.356, 0.579] |
| year | 3 | 12 | 0 | 0 | 1.000 [0.438, 1.000] | 1.000 [0.757, 1.000] | 1.000 [0.757, 1.000] | 1.000 [0.757, 1.000] | 1.000 [0.757, 1.000] | 1.000 [0.757, 1.000] |
| student_type | 3 | 2 | 0 | 2 | 1.000 [0.438, 1.000] | 1.000 [0.342, 1.000] | 0.500 [0.150, 0.850] | 0.500 [0.150, 0.850] | 0.500 [0.150, 0.850] | 0.500 [0.150, 0.850] |
| visa | 2 | 3 | 1 | 0 | 1.000 [0.342, 1.000] | 0.750 [0.301, 0.954] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] |
| topik_level | 12 | 40 | 0 | 10 | 1.000 [0.757, 1.000] | 1.000 [0.912, 1.000] | 0.800 [0.670, 0.888] | 0.800 [0.670, 0.888] | 0.800 [0.670, 0.888] | 0.800 [0.670, 0.888] |
| english_track | 3 | 3 | 0 | 0 | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] |
| academic_status | 32 | 28 | 1 | 2 | 0.906 [0.758, 0.968] | 0.966 [0.828, 0.994] | 0.933 [0.787, 0.982] | 0.933 [0.787, 0.982] | 0.848 [0.691, 0.933] | 0.883 [0.731, 0.954] |
| korean_standard | 3 | 0 | 0 | 4 | 1.000 [0.438, 1.000] | null [null] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] |
| campus | 57 | 55 | 3 | 3 | 1.000 [0.937, 1.000] | 0.948 [0.859, 0.982] | 0.948 [0.859, 0.982] | 0.957 [0.871, 0.987] | 0.948 [0.859, 0.982] | 0.957 [0.871, 0.987] |
| scope | 58 | 57 | 1 | 1 | 1.000 [0.938, 1.000] | 0.983 [0.909, 0.997] | 0.983 [0.909, 0.997] | 0.980 [0.904, 0.996] | 0.983 [0.909, 0.997] | 0.980 [0.904, 0.996] |
| effective_term | 54 | 54 | 0 | 0 | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] |

### erica

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 8 | 15 | 2 | 4 | 1.000 [0.676, 1.000] | 0.882 [0.657, 0.967] | 0.789 [0.567, 0.915] | 0.789 [0.567, 0.915] | 0.789 [0.567, 0.915] | 0.789 [0.567, 0.915] |
| year | 2 | 1 | 0 | 2 | 1.000 [0.342, 1.000] | 1.000 [0.207, 1.000] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] |
| student_type | 3 | 3 | 0 | 2 | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 0.600 [0.231, 0.882] | 0.600 [0.231, 0.882] | 0.600 [0.231, 0.882] | 0.600 [0.231, 0.882] |
| visa | 6 | 6 | 2 | 0 | 1.000 [0.610, 1.000] | 0.750 [0.409, 0.929] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] |
| topik_level | 1 | 3 | 0 | 0 | 1.000 [0.207, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 8 | 8 | 0 | 1 | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] | 0.889 [0.565, 0.980] | 0.889 [0.565, 0.980] | 0.889 [0.565, 0.980] | 0.889 [0.565, 0.980] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 42 | 47 | 0 | 3 | 1.000 [0.916, 1.000] | 1.000 [0.924, 1.000] | 0.940 [0.838, 0.979] | 0.941 [0.839, 0.980] | 0.940 [0.838, 0.979] | 0.941 [0.839, 0.980] |
| scope | 42 | 39 | 3 | 3 | 1.000 [0.916, 1.000] | 0.929 [0.810, 0.975] | 0.929 [0.810, 0.975] | 0.930 [0.811, 0.976] | 0.929 [0.810, 0.975] | 0.930 [0.811, 0.976] |
| effective_term | 12 | 7 | 5 | 5 | 1.000 [0.757, 1.000] | 0.583 [0.320, 0.807] | 0.583 [0.320, 0.807] | 0.523 [0.272, 0.764] | 0.583 [0.320, 0.807] | 0.523 [0.272, 0.764] |

## `any_of` exact match

All chunks: 97/100 (0.97).
Chunks with `any_of` on either side: 2/5 (0.4).

## Disagreement review

Predicted side: 11; reference side: 57; both wrong: 3; ambiguous: 1.
Carried decisions: 0.

## Out-of-vocabulary conditions

| Text | Count |
|---|---:|
| Maximum leave periods, graduate-school type, and consecutive academic probation | 2 |
| Recommendation letter from a Hanyang advisory professor | 2 |
| Scholarship application frequency and duplicate application with the same TOPIK level | 2 |
| Academic transcript and proof of enrollment for the next semester | 1 |
| Applicant and parent citizenship, designated country, and citizenship-renunciation documents | 1 |
| Application, identity, attendance, language-proficiency, employment, employer, and contract documents | 1 |
| Applications and required documents must be accurate and complete | 1 |
| Arrival, quarantine, ID-card collection, and tuition-refund timing | 1 |
| Bachelor's degree or higher and points thresholds; special exemption for a recent Korean degree plus TOPIK level 4 or higher, Social Integration Program stage 4 pass, or stage 5 assignment; professional work experience | 1 |
| Bank-balance amount, document contents, validity, and scholarship-certificate substitution | 1 |
| Citizenship, employment, adoption, and prior-citizenship documents vary by applicant | 1 |
| Consent to personal-information processing and third-party provision | 1 |
| Credit-transfer limits and credit categories | 1 |
| D-2 applicants and holders of other visa types; bank-balance validity, CoA documents, tuition payment, and application deadline | 1 |
| Degree holders, graduates, or expected August 2026 graduates; full-time availability; valid internship visa; preference: business-level language, GKS recipients, or KIIP level 5 | 1 |

## Audience

| Value | Count |
|---|---:|
| applicant | 27 |
| admitted | 6 |
| enrolled | 44 |

## TOPIK scope

| Value | Count |
|---|---:|
| whole_chunk | 13 |
| one_line | 9 |
| null | 78 |
