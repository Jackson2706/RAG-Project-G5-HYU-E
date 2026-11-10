**Limitation (state it in every report):** this is an automated audit. The reference annotator, Codex, also wrote the tagging rules, and the audit is not human-validated.

# Automated applicability tag audit

## G2

| Attribute | Occurrences | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) | Result |
|---|---:|---:|---:|---:|---|
| degree_level | 41 | 0.809 [0.700, 0.885] | 0.753 [0.644, 0.838] | 0.787 [0.680, 0.865] | PASS |
| year | 9 | 0.600 [0.313, 0.832] | 0.375 [0.185, 0.614] | 0.222 [0.085, 0.466] | FAIL |
| student_type | 7 | 0.100 [0.018, 0.404] | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] | FAIL |
| visa | 13 | 0.556 [0.337, 0.754] | 0.769 [0.497, 0.918] | 0.974 [0.734, 0.998] | FAIL |
| topik_level | 24 | 0.841 [0.750, 0.903] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] | PASS |
| english_track | 7 | 0.714 [0.359, 0.918] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | FAIL |
| academic_status | 84 | 0.750 [0.566, 0.873] | 0.250 [0.170, 0.352] | 0.359 [0.265, 0.466] | FAIL |
| campus | 145 | 0.955 [0.909, 0.978] | 0.961 [0.917, 0.982] | 0.953 [0.907, 0.977] | PASS |
| scope | 150 | 0.933 [0.882, 0.963] | 0.933 [0.882, 0.963] | 0.955 [0.909, 0.978] | PASS |
| effective_term | 97 | 0.896 [0.819, 0.942] | 0.887 [0.808, 0.935] | 0.846 [0.761, 0.904] | PASS |

G2 verdict: **FAIL**.

## by method

### rule

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 29 | 50 | 6 | 12 | 0.893 [0.785, 0.950] | 0.806 [0.691, 0.886] | 0.806 [0.691, 0.886] |
| year | 2 | 2 | 0 | 6 | 1.000 [0.342, 1.000] | 0.250 [0.071, 0.591] | 0.250 [0.071, 0.591] |
| student_type | 2 | 1 | 1 | 1 | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] |
| visa | 6 | 7 | 2 | 0 | 0.778 [0.453, 0.937] | 1.000 [0.646, 1.000] | 1.000 [0.646, 1.000] |
| topik_level | 21 | 74 | 11 | 4 | 0.871 [0.783, 0.926] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] |
| english_track | 5 | 5 | 0 | 0 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] |
| academic_status | 47 | 21 | 5 | 27 | 0.808 [0.621, 0.915] | 0.438 [0.307, 0.577] | 0.438 [0.307, 0.577] |
| korean_standard | 1 | 0 | 0 | 1 | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 145 | 147 | 7 | 4 | 0.955 [0.909, 0.978] | 0.974 [0.934, 0.990] | 0.959 [0.914, 0.981] |
| scope | 150 | 140 | 10 | 3 | 0.933 [0.882, 0.963] | 0.979 [0.940, 0.993] | 0.968 [0.925, 0.987] |
| effective_term | 96 | 86 | 10 | 9 | 0.896 [0.819, 0.942] | 0.905 [0.830, 0.949] | 0.859 [0.775, 0.915] |

### llm

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 12 | 5 | 7 | 6 | 0.417 [0.193, 0.680] | 0.455 [0.213, 0.720] | 0.172 [0.047, 0.467] |
| year | 7 | 4 | 4 | 4 | 0.500 [0.215, 0.785] | 0.500 [0.215, 0.785] | 0.122 [0.022, 0.468] |
| student_type | 5 | 0 | 8 | 0 | 0.000 [0.000, 0.324] | null [null] | null [null] |
| visa | 7 | 3 | 6 | 3 | 0.333 [0.121, 0.646] | 0.500 [0.188, 0.812] | 0.523 [0.202, 0.826] |
| topik_level | 3 | 0 | 3 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] |
| english_track | 2 | 0 | 2 | 0 | 0.000 [0.000, 0.658] | null [null] | null [null] |
| academic_status | 37 | 0 | 2 | 36 | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.096] | 0.000 [0.000, 0.096] |
| korean_standard | 3 | 0 | 3 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] |
| campus | 2 | 0 | 0 | 2 | null [null] | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.658] |
| scope | 7 | 0 | 0 | 7 | null [null] | 0.000 [0.000, 0.354] | 0.000 [0.000, 0.354] |
| effective_term | 2 | 0 | 0 | 2 | null [null] | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.658] |


## by bucket

### rule_tagged

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 29 | 50 | 6 | 12 | 0.893 [0.785, 0.950] | 0.806 [0.691, 0.886] | 0.806 [0.691, 0.886] |
| year | 2 | 2 | 0 | 6 | 1.000 [0.342, 1.000] | 0.250 [0.071, 0.591] | 0.250 [0.071, 0.591] |
| student_type | 2 | 1 | 1 | 1 | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] | 0.500 [0.095, 0.905] |
| visa | 6 | 7 | 2 | 0 | 0.778 [0.453, 0.937] | 1.000 [0.646, 1.000] | 1.000 [0.646, 1.000] |
| topik_level | 21 | 74 | 11 | 4 | 0.871 [0.783, 0.926] | 0.949 [0.875, 0.980] | 0.949 [0.875, 0.980] |
| english_track | 5 | 5 | 0 | 0 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] |
| academic_status | 47 | 21 | 5 | 27 | 0.808 [0.621, 0.915] | 0.438 [0.307, 0.577] | 0.438 [0.307, 0.577] |
| korean_standard | 1 | 0 | 0 | 1 | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 52 | 51 | 2 | 4 | 0.962 [0.872, 0.990] | 0.927 [0.827, 0.971] | 0.927 [0.827, 0.971] |
| scope | 54 | 51 | 3 | 3 | 0.944 [0.849, 0.981] | 0.944 [0.849, 0.981] | 0.944 [0.849, 0.981] |
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
| effective_term | 10 | 10 | 0 | 0 | 1.000 [0.722, 1.000] | 1.000 [0.722, 1.000] | 1.000 [0.722, 1.000] |

### llm_tagged

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 9 | 5 | 7 | 1 | 0.417 [0.193, 0.680] | 0.833 [0.436, 0.970] | 0.833 [0.436, 0.970] |
| year | 6 | 4 | 4 | 0 | 0.500 [0.215, 0.785] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] |
| student_type | 5 | 0 | 8 | 0 | 0.000 [0.000, 0.324] | null [null] | null [null] |
| visa | 6 | 3 | 6 | 2 | 0.333 [0.121, 0.646] | 0.600 [0.231, 0.882] | 0.600 [0.231, 0.882] |
| topik_level | 3 | 0 | 3 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] |
| english_track | 2 | 0 | 2 | 0 | 0.000 [0.000, 0.658] | null [null] | null [null] |
| academic_status | 11 | 0 | 2 | 10 | 0.000 [0.000, 0.658] | 0.000 [-0.000, 0.278] | 0.000 [-0.000, 0.278] |
| korean_standard | 3 | 0 | 3 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] |
| campus | 18 | 19 | 2 | 1 | 0.905 [0.711, 0.973] | 0.950 [0.764, 0.991] | 0.950 [0.764, 0.991] |
| scope | 20 | 16 | 4 | 4 | 0.800 [0.584, 0.919] | 0.800 [0.584, 0.919] | 0.800 [0.584, 0.919] |
| effective_term | 13 | 13 | 0 | 0 | 1.000 [0.772, 1.000] | 1.000 [0.772, 1.000] | 1.000 [0.772, 1.000] |

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
| degree_level | 1 | 0 | 0 | 2 | null [null] | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.658] |
| year | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| visa | 1 | 0 | 0 | 1 | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| academic_status | 7 | 0 | 0 | 7 | null [null] | 0.000 [0.000, 0.354] | 0.000 [0.000, 0.354] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| campus | 11 | 12 | 0 | 0 | 1.000 [0.757, 1.000] | 1.000 [0.757, 1.000] | 1.000 [0.757, 1.000] |
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
| degree_level | 30 | 37 | 11 | 13 | 0.771 [0.635, 0.867] | 0.740 [0.604, 0.841] | 0.789 [0.657, 0.879] |
| year | 5 | 4 | 1 | 4 | 0.800 [0.376, 0.964] | 0.500 [0.215, 0.785] | 0.122 [0.022, 0.468] |
| student_type | 5 | 1 | 7 | 0 | 0.125 [0.022, 0.471] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| visa | 8 | 4 | 6 | 3 | 0.400 [0.168, 0.687] | 0.571 [0.250, 0.842] | 0.865 [0.494, 0.977] |
| topik_level | 17 | 67 | 2 | 0 | 0.971 [0.900, 0.992] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] |
| english_track | 5 | 4 | 1 | 0 | 0.800 [0.376, 0.964] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] |
| academic_status | 56 | 12 | 4 | 44 | 0.750 [0.505, 0.898] | 0.214 [0.127, 0.338] | 0.306 [0.201, 0.435] |
| korean_standard | 4 | 0 | 3 | 1 | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 91 | 90 | 6 | 4 | 0.938 [0.870, 0.971] | 0.957 [0.896, 0.983] | 0.955 [0.893, 0.982] |
| scope | 94 | 87 | 7 | 7 | 0.926 [0.854, 0.963] | 0.926 [0.854, 0.963] | 0.969 [0.911, 0.989] |
| effective_term | 79 | 77 | 2 | 2 | 0.975 [0.912, 0.993] | 0.975 [0.912, 0.993] | 0.960 [0.891, 0.986] |

### erica

| Attribute | Occurrences | TP | FP | FN | Precision (95% CI) | Raw recall (95% CI) | Weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 11 | 18 | 2 | 5 | 0.900 [0.699, 0.972] | 0.783 [0.581, 0.903] | 0.783 [0.581, 0.903] |
| year | 4 | 2 | 3 | 6 | 0.400 [0.118, 0.769] | 0.250 [0.071, 0.591] | 0.250 [0.071, 0.591] |
| student_type | 2 | 0 | 2 | 1 | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| visa | 5 | 6 | 2 | 0 | 0.750 [0.409, 0.929] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] |
| topik_level | 7 | 7 | 12 | 4 | 0.368 [0.191, 0.590] | 0.636 [0.354, 0.848] | 0.636 [0.354, 0.848] |
| english_track | 2 | 1 | 1 | 0 | 0.500 [0.095, 0.905] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| academic_status | 28 | 9 | 3 | 19 | 0.750 [0.468, 0.911] | 0.321 [0.179, 0.507] | 0.470 [0.300, 0.647] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] |
| campus | 54 | 57 | 1 | 2 | 0.983 [0.909, 0.997] | 0.966 [0.885, 0.991] | 0.950 [0.862, 0.983] |
| scope | 56 | 53 | 3 | 3 | 0.946 [0.854, 0.982] | 0.946 [0.854, 0.982] | 0.933 [0.836, 0.974] |
| effective_term | 18 | 9 | 8 | 9 | 0.529 [0.310, 0.738] | 0.500 [0.290, 0.710] | 0.459 [0.257, 0.675] |

## `any_of` exact match

All chunks: 148/150 (0.9866666666666667).
Chunks with `any_of` on either side: 4/6 (0.6666666666666666).

## Disagreement review

Predicted side: 18; reference side: 147; both wrong: 5; ambiguous: 7.

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
