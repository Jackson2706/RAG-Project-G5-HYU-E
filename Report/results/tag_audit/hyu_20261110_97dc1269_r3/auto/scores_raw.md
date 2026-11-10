**Limitation (state it in every report):** this is an automated audit. The reference annotator, Codex, also wrote the tagging rules, and the audit is not human-validated.

# Automated applicability tag audit

## G2

| Attribute | Occurrences | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) | Result |
|---|---:|---:|---:|---:|---|
| degree_level | 47 | 0.765 [0.651, 0.850] | 0.667 [0.556, 0.761] | 0.775 [0.671, 0.853] | FAIL |
| year | 9 | 0.600 [0.313, 0.832] | 0.375 [0.185, 0.614] | 0.222 [0.085, 0.466] | FAIL |
| student_type | 7 | 0.000 [-0.000, 0.278] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | FAIL |
| visa | 13 | 0.500 [0.290, 0.710] | 0.692 [0.424, 0.873] | 0.857 [0.590, 0.962] | FAIL |
| topik_level | 25 | 0.841 [0.750, 0.903] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] | PASS |
| english_track | 7 | 0.714 [0.359, 0.918] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | FAIL |
| academic_status | 84 | 0.643 [0.458, 0.793] | 0.222 [0.145, 0.324] | 0.325 [0.233, 0.433] | FAIL |
| campus | 150 | 0.932 [0.883, 0.962] | 0.950 [0.904, 0.974] | 0.944 [0.897, 0.970] | PASS |
| scope | 150 | 0.913 [0.857, 0.949] | 0.913 [0.857, 0.949] | 0.943 [0.893, 0.970] | PASS |
| effective_term | 99 | 0.878 [0.798, 0.929] | 0.869 [0.788, 0.922] | 0.834 [0.749, 0.895] | PASS |

G2 verdict: **FAIL**.

## by method

### rule

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 29 | 45 | 11 | 11 | 0.804 [0.682, 0.887] | 0.804 [0.682, 0.887] | 0.804 [0.682, 0.887] |
| year | 2 | 2 | 0 | 6 | 1.000 [0.342, 1.000] | 0.250 [0.071, 0.591] | 0.250 [0.071, 0.591] |
| student_type | 2 | 0 | 2 | 1 | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| visa | 6 | 7 | 2 | 1 | 0.778 [0.453, 0.937] | 0.875 [0.529, 0.978] | 0.875 [0.529, 0.978] |
| topik_level | 22 | 74 | 11 | 8 | 0.871 [0.783, 0.926] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] |
| english_track | 5 | 5 | 0 | 0 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] |
| academic_status | 47 | 18 | 8 | 27 | 0.692 [0.500, 0.835] | 0.400 [0.270, 0.545] | 0.400 [0.270, 0.545] |
| korean_standard | 1 | 0 | 0 | 1 | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 150 | 151 | 11 | 5 | 0.932 [0.883, 0.962] | 0.968 [0.927, 0.986] | 0.950 [0.904, 0.975] |
| scope | 150 | 137 | 13 | 4 | 0.913 [0.857, 0.949] | 0.972 [0.929, 0.989] | 0.957 [0.910, 0.980] |
| effective_term | 98 | 86 | 12 | 10 | 0.878 [0.798, 0.929] | 0.896 [0.819, 0.942] | 0.848 [0.763, 0.906] |

### llm

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 18 | 7 | 5 | 15 | 0.583 [0.320, 0.807] | 0.318 [0.164, 0.527] | 0.180 [0.072, 0.383] |
| year | 7 | 4 | 4 | 4 | 0.500 [0.215, 0.785] | 0.500 [0.215, 0.785] | 0.122 [0.022, 0.468] |
| student_type | 5 | 0 | 8 | 0 | 0.000 [0.000, 0.324] | null [null] | null [null] |
| visa | 7 | 2 | 7 | 3 | 0.222 [0.063, 0.547] | 0.400 [0.118, 0.769] | 0.422 [0.129, 0.783] |
| topik_level | 3 | 0 | 3 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] |
| english_track | 2 | 0 | 2 | 0 | 0.000 [0.000, 0.658] | null [null] | null [null] |
| academic_status | 37 | 0 | 2 | 36 | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.096] | 0.000 [0.000, 0.096] |
| korean_standard | 3 | 0 | 3 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] |
| campus | 3 | 0 | 0 | 3 | null [null] | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.562] |
| scope | 9 | 0 | 0 | 9 | null [null] | 0.000 [0.000, 0.299] | 0.000 [0.000, 0.299] |
| effective_term | 3 | 0 | 0 | 3 | null [null] | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.562] |


## by bucket

### rule_tagged

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 29 | 45 | 11 | 11 | 0.804 [0.682, 0.887] | 0.804 [0.682, 0.887] | 0.804 [0.682, 0.887] |
| year | 2 | 2 | 0 | 6 | 1.000 [0.342, 1.000] | 0.250 [0.071, 0.591] | 0.250 [0.071, 0.591] |
| student_type | 2 | 0 | 2 | 1 | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| visa | 6 | 7 | 2 | 1 | 0.778 [0.453, 0.937] | 0.875 [0.529, 0.978] | 0.875 [0.529, 0.978] |
| topik_level | 22 | 74 | 11 | 8 | 0.871 [0.783, 0.926] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] |
| english_track | 5 | 5 | 0 | 0 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] |
| academic_status | 47 | 18 | 8 | 27 | 0.692 [0.500, 0.835] | 0.400 [0.270, 0.545] | 0.400 [0.270, 0.545] |
| korean_standard | 1 | 0 | 0 | 1 | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 54 | 53 | 3 | 5 | 0.946 [0.854, 0.982] | 0.914 [0.814, 0.963] | 0.914 [0.814, 0.963] |
| scope | 54 | 50 | 4 | 4 | 0.926 [0.824, 0.971] | 0.926 [0.824, 0.971] | 0.926 [0.824, 0.971] |
| effective_term | 45 | 36 | 9 | 9 | 0.800 [0.662, 0.891] | 0.800 [0.662, 0.891] | 0.800 [0.662, 0.891] |

### rule_unconditioned

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| academic_status | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| campus | 25 | 26 | 0 | 0 | 1.000 [0.871, 1.000] | 1.000 [0.871, 1.000] | 1.000 [0.871, 1.000] |
| scope | 25 | 25 | 0 | 0 | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] | 1.000 [0.867, 1.000] |
| effective_term | 11 | 10 | 1 | 1 | 0.909 [0.623, 0.984] | 0.909 [0.623, 0.984] | 0.909 [0.623, 0.984] |

### llm_tagged

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 12 | 7 | 5 | 6 | 0.583 [0.320, 0.807] | 0.538 [0.291, 0.768] | 0.538 [0.291, 0.768] |
| year | 6 | 4 | 4 | 0 | 0.500 [0.215, 0.785] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] |
| student_type | 5 | 0 | 8 | 0 | 0.000 [0.000, 0.324] | null [null] | null [null] |
| visa | 6 | 2 | 7 | 2 | 0.222 [0.063, 0.547] | 0.500 [0.150, 0.850] | 0.500 [0.150, 0.850] |
| topik_level | 3 | 0 | 3 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] |
| english_track | 2 | 0 | 2 | 0 | 0.000 [0.000, 0.658] | null [null] | null [null] |
| academic_status | 11 | 0 | 2 | 10 | 0.000 [0.000, 0.658] | 0.000 [-0.000, 0.278] | 0.000 [-0.000, 0.278] |
| korean_standard | 3 | 0 | 3 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] |
| campus | 20 | 20 | 4 | 2 | 0.833 [0.641, 0.933] | 0.909 [0.722, 0.975] | 0.909 [0.722, 0.975] |
| scope | 20 | 14 | 6 | 6 | 0.700 [0.481, 0.855] | 0.700 [0.481, 0.855] | 0.700 [0.481, 0.855] |
| effective_term | 14 | 13 | 1 | 1 | 0.929 [0.685, 0.987] | 0.929 [0.685, 0.987] | 0.929 [0.685, 0.987] |

### llm_unconditioned

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 2 | 0 | 0 | 3 | null [null] | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.562] |
| year | 1 | 0 | 0 | 4 | null [null] | 0.000 [0.000, 0.490] | 0.000 [0.000, 0.490] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| academic_status | 19 | 0 | 0 | 19 | null [null] | 0.000 [0.000, 0.168] | 0.000 [0.000, 0.168] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| campus | 39 | 39 | 3 | 1 | 0.929 [0.810, 0.975] | 0.975 [0.871, 0.996] | 0.975 [0.871, 0.996] |
| scope | 39 | 37 | 2 | 2 | 0.949 [0.831, 0.986] | 0.949 [0.831, 0.986] | 0.949 [0.831, 0.986] |
| effective_term | 21 | 19 | 1 | 2 | 0.950 [0.764, 0.991] | 0.905 [0.711, 0.973] | 0.905 [0.711, 0.973] |

### llm_rejected

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 4 | 0 | 0 | 6 | null [null] | 0.000 [0.000, 0.390] | 0.000 [0.000, 0.390] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| visa | 1 | 0 | 0 | 1 | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| academic_status | 7 | 0 | 0 | 7 | null [null] | 0.000 [0.000, 0.354] | 0.000 [0.000, 0.354] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| campus | 12 | 13 | 1 | 0 | 0.929 [0.685, 0.987] | 1.000 [0.772, 1.000] | 1.000 [0.772, 1.000] |
| scope | 12 | 11 | 1 | 1 | 0.917 [0.646, 0.985] | 0.917 [0.646, 0.985] | 0.917 [0.646, 0.985] |
| effective_term | 8 | 8 | 0 | 0 | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] |

### llm_errors

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| visa | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| academic_status | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| campus | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| scope | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| effective_term | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |


## by campus

### seoul

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 36 | 34 | 14 | 21 | 0.708 [0.568, 0.818] | 0.618 [0.486, 0.735] | 0.770 [0.644, 0.861] |
| year | 5 | 4 | 1 | 4 | 0.800 [0.376, 0.964] | 0.500 [0.215, 0.785] | 0.122 [0.022, 0.468] |
| student_type | 5 | 0 | 8 | 0 | 0.000 [0.000, 0.324] | null [null] | null [null] |
| visa | 8 | 3 | 7 | 3 | 0.300 [0.108, 0.603] | 0.500 [0.188, 0.812] | 0.858 [0.459, 0.977] |
| topik_level | 17 | 67 | 2 | 0 | 0.971 [0.900, 0.992] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] |
| english_track | 5 | 4 | 1 | 0 | 0.800 [0.376, 0.964] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] |
| academic_status | 56 | 9 | 7 | 44 | 0.562 [0.332, 0.769] | 0.170 [0.092, 0.292] | 0.248 [0.152, 0.379] |
| korean_standard | 4 | 0 | 3 | 1 | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 94 | 92 | 10 | 4 | 0.902 [0.829, 0.946] | 0.958 [0.898, 0.984] | 0.956 [0.895, 0.983] |
| scope | 94 | 86 | 8 | 8 | 0.915 [0.841, 0.956] | 0.915 [0.841, 0.956] | 0.967 [0.909, 0.989] |
| effective_term | 81 | 77 | 4 | 4 | 0.951 [0.880, 0.981] | 0.951 [0.880, 0.981] | 0.944 [0.870, 0.977] |

### erica

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 11 | 18 | 2 | 5 | 0.900 [0.699, 0.972] | 0.783 [0.581, 0.903] | 0.783 [0.581, 0.903] |
| year | 4 | 2 | 3 | 6 | 0.400 [0.118, 0.769] | 0.250 [0.071, 0.591] | 0.250 [0.071, 0.591] |
| student_type | 2 | 0 | 2 | 1 | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| visa | 5 | 6 | 2 | 1 | 0.750 [0.409, 0.929] | 0.857 [0.487, 0.974] | 0.857 [0.487, 0.974] |
| topik_level | 8 | 7 | 12 | 8 | 0.368 [0.191, 0.590] | 0.467 [0.248, 0.699] | 0.467 [0.248, 0.699] |
| english_track | 2 | 1 | 1 | 0 | 0.500 [0.095, 0.905] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| academic_status | 28 | 9 | 3 | 19 | 0.750 [0.468, 0.911] | 0.321 [0.179, 0.507] | 0.470 [0.300, 0.647] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| campus | 56 | 59 | 1 | 4 | 0.983 [0.911, 0.997] | 0.937 [0.848, 0.975] | 0.927 [0.836, 0.970] |
| scope | 56 | 51 | 5 | 5 | 0.911 [0.807, 0.961] | 0.911 [0.807, 0.961] | 0.904 [0.799, 0.957] |
| effective_term | 18 | 9 | 8 | 9 | 0.529 [0.310, 0.738] | 0.500 [0.290, 0.710] | 0.459 [0.257, 0.675] |

## `any_of` exact match

All chunks: 148/150 (0.9866666666666667).
Chunks with `any_of` on either side: 4/6 (0.6666666666666666).
