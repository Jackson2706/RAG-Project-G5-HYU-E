**Limitation (state it in every report):** this is an automated audit. The reference annotator, Codex, also wrote the tagging rules, and the audit is not human-validated.

# Automated applicability tag audit

## G2

| Attribute | Occurrences | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| degree_level | 37 | 1.000 [0.906, 1.000] | 0.833 [0.713, 0.910] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] | FAIL |
| topik_level | 13 | 1.000 [0.772, 1.000] | 1.000 [0.918, 1.000] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | PASS |
| academic_status | 41 | 0.902 [0.775, 0.961] | 0.973 [0.862, 0.995] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] | 0.837 [0.700, 0.919] | 0.872 [0.741, 0.942] | PASS |
| campus | 100 | 1.000 [0.963, 1.000] | 0.963 [0.908, 0.985] | 0.945 [0.885, 0.975] | 0.951 [0.892, 0.978] | 0.945 [0.885, 0.975] | 0.951 [0.892, 0.978] | PASS |
| scope | 100 | 1.000 [0.963, 1.000] | 0.960 [0.902, 0.984] | 0.960 [0.902, 0.984] | 0.960 [0.901, 0.984] | 0.960 [0.902, 0.984] | 0.960 [0.901, 0.984] | PASS |
| effective_term | 66 | 1.000 [0.945, 1.000] | 0.924 [0.835, 0.967] | 0.924 [0.835, 0.967] | 0.913 [0.821, 0.960] | 0.924 [0.835, 0.967] | 0.913 [0.821, 0.960] | PASS |

G2 verdict: **FAIL**.

## Unknown-condition estimate

Reference-conditioned unknown chunks: 4/30 (0.133 [0.053, 0.297]).
Estimated conditioned chunks among 387 index unknowns: 51.6 [20.5, 114.9].
Top attributes: academic_status (4).

## by method

### rule

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 37 | 45 | 9 | 41 | 1.000 [0.906, 1.000] | 0.833 [0.713, 0.910] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] |
| year | 4 | 12 | 1 | 2 | 1.000 [0.510, 1.000] | 0.923 [0.667, 0.986] | 0.857 [0.601, 0.960] | 0.857 [0.601, 0.960] | 0.857 [0.601, 0.960] | 0.857 [0.601, 0.960] |
| student_type | 3 | 1 | 4 | 2 | 1.000 [0.438, 1.000] | 0.200 [0.036, 0.624] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] |
| visa | 2 | 2 | 10 | 0 | 1.000 [0.342, 1.000] | 0.167 [0.047, 0.448] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] |
| topik_level | 13 | 43 | 0 | 10 | 1.000 [0.772, 1.000] | 1.000 [0.918, 1.000] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] |
| english_track | 3 | 3 | 0 | 0 | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] |
| academic_status | 41 | 36 | 1 | 3 | 0.902 [0.775, 0.961] | 0.973 [0.862, 0.995] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] | 0.837 [0.700, 0.919] | 0.872 [0.741, 0.942] |
| korean_standard | 3 | 0 | 0 | 4 | 1.000 [0.438, 1.000] | null [null] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] |
| campus | 100 | 103 | 4 | 6 | 1.000 [0.963, 1.000] | 0.963 [0.908, 0.985] | 0.945 [0.885, 0.975] | 0.951 [0.892, 0.978] | 0.945 [0.885, 0.975] | 0.951 [0.892, 0.978] |
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
| degree_level | 37 | 45 | 9 | 41 | 1.000 [0.906, 1.000] | 0.833 [0.713, 0.910] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] | 0.523 [0.419, 0.626] |
| year | 4 | 12 | 1 | 2 | 1.000 [0.510, 1.000] | 0.923 [0.667, 0.986] | 0.857 [0.601, 0.960] | 0.857 [0.601, 0.960] | 0.857 [0.601, 0.960] | 0.857 [0.601, 0.960] |
| student_type | 3 | 1 | 4 | 2 | 1.000 [0.438, 1.000] | 0.200 [0.036, 0.624] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] | 0.333 [0.061, 0.792] |
| visa | 2 | 2 | 10 | 0 | 1.000 [0.342, 1.000] | 0.167 [0.047, 0.448] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] |
| topik_level | 13 | 43 | 0 | 10 | 1.000 [0.772, 1.000] | 1.000 [0.918, 1.000] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] | 0.811 [0.686, 0.894] |
| english_track | 3 | 3 | 0 | 0 | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] |
| academic_status | 37 | 36 | 1 | 3 | 1.000 [0.906, 1.000] | 0.973 [0.862, 0.995] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] | 0.923 [0.797, 0.973] |
| korean_standard | 3 | 0 | 0 | 4 | 1.000 [0.438, 1.000] | null [null] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] |
| campus | 53 | 56 | 2 | 2 | 1.000 [0.932, 1.000] | 0.966 [0.883, 0.990] | 0.966 [0.883, 0.990] | 0.966 [0.883, 0.990] | 0.966 [0.883, 0.990] | 0.966 [0.883, 0.990] |
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
| academic_status | 4 | 0 | 0 | 0 | 0.000 [0.000, 0.490] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] |
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
| student_type | 2 | 1 | 1 | 1 | 1.000 [0.342, 1.000] | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] |
| visa | 0 | 0 | 4 | 0 | null [null] | 0.000 [0.000, 0.490] | null [null] | null [null] | null [null] | null [null] |
| topik_level | 12 | 40 | 0 | 10 | 1.000 [0.757, 1.000] | 1.000 [0.912, 1.000] | 0.800 [0.670, 0.888] | 0.800 [0.670, 0.888] | 0.800 [0.670, 0.888] | 0.800 [0.670, 0.888] |
| english_track | 3 | 3 | 0 | 0 | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] | 1.000 [0.438, 1.000] |
| academic_status | 33 | 28 | 1 | 2 | 0.879 [0.727, 0.952] | 0.966 [0.828, 0.994] | 0.933 [0.787, 0.982] | 0.933 [0.787, 0.982] | 0.824 [0.665, 0.917] | 0.867 [0.715, 0.944] |
| korean_standard | 3 | 0 | 0 | 4 | 1.000 [0.438, 1.000] | null [null] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] |
| campus | 58 | 56 | 4 | 3 | 1.000 [0.938, 1.000] | 0.933 [0.841, 0.974] | 0.949 [0.861, 0.983] | 0.958 [0.873, 0.987] | 0.949 [0.861, 0.983] | 0.958 [0.873, 0.987] |
| scope | 58 | 57 | 1 | 1 | 1.000 [0.938, 1.000] | 0.983 [0.909, 0.997] | 0.983 [0.909, 0.997] | 0.980 [0.904, 0.996] | 0.983 [0.909, 0.997] | 0.980 [0.904, 0.996] |
| effective_term | 54 | 54 | 0 | 0 | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] | 1.000 [0.934, 1.000] |

### erica

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 5 | 11 | 6 | 2 | 1.000 [0.566, 1.000] | 0.647 [0.413, 0.827] | 0.846 [0.578, 0.957] | 0.846 [0.578, 0.957] | 0.846 [0.578, 0.957] | 0.846 [0.578, 0.957] |
| year | 1 | 0 | 1 | 2 | 1.000 [0.207, 1.000] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.658] |
| student_type | 1 | 0 | 3 | 1 | 1.000 [0.207, 1.000] | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| visa | 2 | 2 | 6 | 0 | 1.000 [0.342, 1.000] | 0.250 [0.071, 0.591] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] | 1.000 [0.342, 1.000] |
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
