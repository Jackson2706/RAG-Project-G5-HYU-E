**Limitation (state it in every report):** this is an automated audit. The reference annotator, Codex, also wrote the tagging rules, and the audit is not human-validated.

# Automated applicability tag audit

## G2

| Attribute | Occurrences | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| degree_level | 39 | 0.718 [0.562, 0.835] | 0.818 [0.697, 0.898] | 0.726 [0.604, 0.821] | 0.726 [0.604, 0.821] | 0.577 [0.466, 0.680] | 0.667 [0.557, 0.762] | PASS |
| year | 6 | 0.667 [0.300, 0.903] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 0.875 [0.640, 0.965] | 0.954 [0.738, 0.993] | PASS |
| visa | 9 | 0.667 [0.354, 0.879] | 0.857 [0.487, 0.974] | 0.600 [0.313, 0.832] | 0.600 [0.313, 0.832] | 0.462 [0.232, 0.709] | 0.544 [0.296, 0.772] | FAIL |
| topik_level | 18 | 1.000 [0.824, 1.000] | 0.925 [0.846, 0.965] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] | PASS |
| english_track | 5 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | PASS |
| academic_status | 60 | 0.850 [0.739, 0.919] | 0.979 [0.891, 0.996] | 0.904 [0.794, 0.958] | 0.904 [0.794, 0.958] | 0.770 [0.651, 0.858] | 0.853 [0.744, 0.921] | PASS |
| campus | 150 | 1.000 [0.975, 1.000] | 0.932 [0.883, 0.962] | 0.950 [0.904, 0.974] | 0.945 [0.898, 0.971] | 0.950 [0.904, 0.974] | 0.945 [0.898, 0.971] | PASS |
| scope | 150 | 1.000 [0.975, 1.000] | 0.913 [0.857, 0.949] | 0.913 [0.857, 0.949] | 0.925 [0.872, 0.958] | 0.913 [0.857, 0.949] | 0.925 [0.872, 0.958] | PASS |
| effective_term | 99 | 1.000 [0.963, 1.000] | 0.878 [0.798, 0.929] | 0.869 [0.788, 0.922] | 0.843 [0.759, 0.902] | 0.869 [0.788, 0.922] | 0.843 [0.759, 0.902] | PASS |

G2 verdict: **FAIL**.

## Unknown-condition estimate

Reference-conditioned unknown chunks: 20/63 (0.317 [0.216, 0.440]).
Estimated conditioned chunks among 387 index unknowns: 122.9 [83.5, 170.3].
Top attributes: degree_level (11), academic_status (9), visa (3), year (2).

## by method

### rule

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 39 | 45 | 10 | 17 | 0.718 [0.562, 0.835] | 0.818 [0.697, 0.898] | 0.726 [0.604, 0.821] | 0.726 [0.604, 0.821] | 0.577 [0.466, 0.680] | 0.667 [0.557, 0.762] |
| year | 6 | 14 | 0 | 0 | 0.667 [0.300, 0.903] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 0.875 [0.640, 0.965] | 0.954 [0.738, 0.993] |
| student_type | 1 | 1 | 1 | 0 | 1.000 [0.207, 1.000] | 0.500 [0.095, 0.905] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| visa | 9 | 6 | 1 | 4 | 0.667 [0.354, 0.879] | 0.857 [0.487, 0.974] | 0.600 [0.313, 0.832] | 0.600 [0.313, 0.832] | 0.462 [0.232, 0.709] | 0.544 [0.296, 0.772] |
| topik_level | 18 | 74 | 6 | 8 | 1.000 [0.824, 1.000] | 0.925 [0.846, 0.965] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] |
| english_track | 5 | 5 | 0 | 0 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] |
| academic_status | 60 | 47 | 1 | 5 | 0.850 [0.739, 0.919] | 0.979 [0.891, 0.996] | 0.904 [0.794, 0.958] | 0.904 [0.794, 0.958] | 0.770 [0.651, 0.858] | 0.853 [0.744, 0.921] |
| korean_standard | 1 | 0 | 0 | 1 | 1.000 [0.207, 1.000] | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 150 | 151 | 11 | 8 | 1.000 [0.975, 1.000] | 0.932 [0.883, 0.962] | 0.950 [0.904, 0.974] | 0.945 [0.898, 0.971] | 0.950 [0.904, 0.974] | 0.945 [0.898, 0.971] |
| scope | 150 | 137 | 13 | 13 | 1.000 [0.975, 1.000] | 0.913 [0.857, 0.949] | 0.913 [0.857, 0.949] | 0.925 [0.872, 0.958] | 0.913 [0.857, 0.949] | 0.925 [0.872, 0.958] |
| effective_term | 99 | 86 | 12 | 13 | 1.000 [0.963, 1.000] | 0.878 [0.798, 0.929] | 0.869 [0.788, 0.922] | 0.843 [0.759, 0.902] | 0.869 [0.788, 0.922] | 0.843 [0.759, 0.902] |

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
| degree_level | 28 | 45 | 10 | 17 | 1.000 [0.879, 1.000] | 0.818 [0.697, 0.898] | 0.726 [0.604, 0.821] | 0.726 [0.604, 0.821] | 0.726 [0.604, 0.821] | 0.726 [0.604, 0.821] |
| year | 4 | 14 | 0 | 0 | 1.000 [0.510, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] |
| student_type | 1 | 1 | 1 | 0 | 1.000 [0.207, 1.000] | 0.500 [0.095, 0.905] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| visa | 6 | 6 | 1 | 4 | 1.000 [0.610, 1.000] | 0.857 [0.487, 0.974] | 0.600 [0.313, 0.832] | 0.600 [0.313, 0.832] | 0.600 [0.313, 0.832] | 0.600 [0.313, 0.832] |
| topik_level | 18 | 74 | 6 | 8 | 1.000 [0.824, 1.000] | 0.925 [0.846, 0.965] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] | 0.902 [0.819, 0.950] |
| english_track | 5 | 5 | 0 | 0 | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] | 1.000 [0.566, 1.000] |
| academic_status | 51 | 47 | 1 | 5 | 1.000 [0.930, 1.000] | 0.979 [0.891, 0.996] | 0.904 [0.794, 0.958] | 0.904 [0.794, 0.958] | 0.904 [0.794, 0.958] | 0.904 [0.794, 0.958] |
| korean_standard | 1 | 0 | 0 | 1 | 1.000 [0.207, 1.000] | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 66 | 65 | 4 | 5 | 1.000 [0.945, 1.000] | 0.942 [0.860, 0.977] | 0.929 [0.843, 0.969] | 0.929 [0.843, 0.969] | 0.929 [0.843, 0.969] | 0.929 [0.843, 0.969] |
| scope | 66 | 61 | 5 | 5 | 1.000 [0.945, 1.000] | 0.924 [0.835, 0.967] | 0.924 [0.835, 0.967] | 0.924 [0.835, 0.967] | 0.924 [0.835, 0.967] | 0.924 [0.835, 0.967] |
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
| effective_term | 7 | 6 | 1 | 1 | 1.000 [0.646, 1.000] | 0.857 [0.487, 0.974] | 0.857 [0.487, 0.974] | 0.857 [0.487, 0.974] | 0.857 [0.487, 0.974] | 0.857 [0.487, 0.974] |

### rule_cue_unknown

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 11 | 0 | 0 | 0 | 0.000 [0.000, 0.259] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.194] | 0.000 [0.000, 0.194] |
| year | 2 | 0 | 0 | 0 | 0.000 [0.000, 0.658] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.658] | 0.000 [0.000, 0.658] |
| student_type | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| visa | 3 | 0 | 0 | 0 | 0.000 [0.000, 0.562] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.562] | 0.000 [0.000, 0.562] |
| topik_level | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| english_track | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| academic_status | 9 | 0 | 0 | 0 | 0.000 [0.000, 0.299] | null [null] | null [null] | null [null] | 0.000 [0.000, 0.299] | 0.000 [0.000, 0.299] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 63 | 64 | 7 | 3 | 1.000 [0.943, 1.000] | 0.901 [0.810, 0.951] | 0.955 [0.876, 0.985] | 0.955 [0.876, 0.985] | 0.955 [0.876, 0.985] | 0.955 [0.876, 0.985] |
| scope | 63 | 55 | 8 | 8 | 1.000 [0.943, 1.000] | 0.873 [0.769, 0.934] | 0.873 [0.769, 0.934] | 0.873 [0.769, 0.934] | 0.873 [0.769, 0.934] | 0.873 [0.769, 0.934] |
| effective_term | 37 | 35 | 1 | 2 | 1.000 [0.906, 1.000] | 0.972 [0.858, 0.995] | 0.946 [0.823, 0.985] | 0.946 [0.823, 0.985] | 0.946 [0.823, 0.985] | 0.946 [0.823, 0.985] |

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
| degree_level | 30 | 27 | 10 | 12 | 0.633 [0.455, 0.781] | 0.730 [0.570, 0.846] | 0.692 [0.536, 0.814] | 0.692 [0.536, 0.814] | 0.491 [0.364, 0.619] | 0.607 [0.475, 0.725] |
| year | 4 | 6 | 0 | 0 | 0.500 [0.150, 0.850] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 1.000 [0.610, 1.000] | 0.750 [0.409, 0.929] | 0.898 [0.553, 0.984] |
| student_type | 0 | 0 | 1 | 0 | null [null] | 0.000 [0.000, 0.793] | null [null] | null [null] | null [null] | null [null] |
| visa | 5 | 2 | 0 | 1 | 0.400 [0.118, 0.769] | 1.000 [0.342, 1.000] | 0.667 [0.208, 0.939] | 0.667 [0.208, 0.939] | 0.333 [0.097, 0.700] | 0.497 [0.186, 0.811] |
| topik_level | 15 | 67 | 0 | 0 | 1.000 [0.796, 1.000] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] | 1.000 [0.946, 1.000] |
| english_track | 4 | 4 | 0 | 0 | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] | 1.000 [0.510, 1.000] |
| academic_status | 45 | 33 | 1 | 5 | 0.822 [0.687, 0.907] | 0.971 [0.851, 0.995] | 0.868 [0.727, 0.942] | 0.868 [0.727, 0.942] | 0.717 [0.575, 0.827] | 0.810 [0.675, 0.898] |
| korean_standard | 1 | 0 | 0 | 1 | 1.000 [0.207, 1.000] | null [null] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.793] |
| campus | 94 | 92 | 10 | 4 | 1.000 [0.961, 1.000] | 0.902 [0.829, 0.946] | 0.958 [0.898, 0.984] | 0.960 [0.900, 0.985] | 0.958 [0.898, 0.984] | 0.960 [0.900, 0.985] |
| scope | 94 | 86 | 8 | 8 | 1.000 [0.961, 1.000] | 0.915 [0.841, 0.956] | 0.915 [0.841, 0.956] | 0.939 [0.871, 0.972] | 0.915 [0.841, 0.956] | 0.939 [0.871, 0.972] |
| effective_term | 81 | 77 | 4 | 4 | 1.000 [0.955, 1.000] | 0.951 [0.880, 0.981] | 0.951 [0.880, 0.981] | 0.946 [0.874, 0.978] | 0.951 [0.880, 0.981] | 0.946 [0.874, 0.978] |

### erica

| Attribute | Occurrences | TP | FP | FN | Coverage (95% CI) | Resolved precision (95% CI) | Resolved recall (95% CI) | Resolved weighted recall (95% CI) | Strict recall (95% CI) | Strict weighted recall (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| degree_level | 9 | 18 | 0 | 5 | 1.000 [0.701, 1.000] | 1.000 [0.824, 1.000] | 0.783 [0.581, 0.903] | 0.783 [0.581, 0.903] | 0.783 [0.581, 0.903] | 0.783 [0.581, 0.903] |
| year | 2 | 8 | 0 | 0 | 1.000 [0.342, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] | 1.000 [0.676, 1.000] |
| student_type | 1 | 1 | 0 | 0 | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| visa | 4 | 4 | 1 | 3 | 1.000 [0.510, 1.000] | 0.800 [0.376, 0.964] | 0.571 [0.250, 0.842] | 0.571 [0.250, 0.842] | 0.571 [0.250, 0.842] | 0.571 [0.250, 0.842] |
| topik_level | 3 | 7 | 6 | 8 | 1.000 [0.438, 1.000] | 0.538 [0.291, 0.768] | 0.467 [0.248, 0.699] | 0.467 [0.248, 0.699] | 0.467 [0.248, 0.699] | 0.467 [0.248, 0.699] |
| english_track | 1 | 1 | 0 | 0 | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] | 1.000 [0.207, 1.000] |
| academic_status | 15 | 14 | 0 | 0 | 0.933 [0.702, 0.988] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 1.000 [0.785, 1.000] | 0.933 [0.702, 0.988] | 0.976 [0.760, 0.998] |
| korean_standard | 0 | 0 | 0 | 0 | null [null] | null [null] | null [null] | null [null] | null [null] | null [null] |
| campus | 56 | 59 | 1 | 4 | 1.000 [0.936, 1.000] | 0.983 [0.911, 0.997] | 0.937 [0.848, 0.975] | 0.922 [0.829, 0.966] | 0.937 [0.848, 0.975] | 0.922 [0.829, 0.966] |
| scope | 56 | 51 | 5 | 5 | 1.000 [0.936, 1.000] | 0.911 [0.807, 0.961] | 0.911 [0.807, 0.961] | 0.901 [0.795, 0.955] | 0.911 [0.807, 0.961] | 0.901 [0.795, 0.955] |
| effective_term | 18 | 9 | 8 | 9 | 1.000 [0.824, 1.000] | 0.529 [0.310, 0.738] | 0.500 [0.290, 0.710] | 0.449 [0.249, 0.667] | 0.500 [0.290, 0.710] | 0.449 [0.249, 0.667] |

## `any_of` exact match

All chunks: 148/150 (0.9866666666666667).
Chunks with `any_of` on either side: 4/6 (0.6666666666666666).
