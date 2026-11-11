# Codex annotation notes

## Batch status

- Batch 01: done; `labeling.validate --annotation` exited 0 with no output.
- Batch 02: done; `labeling.validate --annotation` exited 0 with no output.
- Batch 03: done; `labeling.validate --annotation` exited 0 with no output.
- Batch 04: not done.
- Batch 05: not done.
- Batch 06: not done.

## Batch 01

Hard cases:

- T14-009 says the student was accepted, but the fixed input `gold_profile` says `academic_status: applicant`. The validator requires stated values to agree with the gold profile, so the conflicting stated status is omitted and the mismatch is documented in the row.
- T14-031 and T14-033 rely on a Seoul re-registration PDF whose screenshot-based portal steps did not extract completely. They are labeled partial where the English text supports dates and online-only handling but not a complete menu path.
- T14-035 uses the national immigration consequence stated in the ERICA leave guide for the Seoul gold profile, following the guideline that national immigration rules apply across campuses.
- T14-027 is a past January 2026 event and excludes the gold-profile exchange student, so the answer does not present the old form as active.

Guideline questions:

- When the question explicitly states an academic status that conflicts with the immutable input `gold_profile`, should adjudication correct the persona/case pair, or should the stated field continue to be omitted to satisfy validation?

## Batch 02

Hard cases:

- T14-046's only matching monthly counseling notice is limited to master's and doctoral students, while the gold profile is a non-degree visitor. The restricting span is treated as gold evidence because it establishes ineligibility.
- T14-050 is partial because the dormitory page exposes specific activity rooms and a cafeteria but not a complete facilities inventory.
- T14-067 and T14-068 have a completed-coursework gold profile, while the career and counseling pages use broad graduate-student or international-student wording without explicitly confirming completed-coursework eligibility.
- T14-062 does not use `condition_sets`: HIEA accepts IELTS or TOEFL for English-track students in place of TOPIK, but the source expresses this as a parenthetical substitution and does not use “or” between AAES condition sets as required by the guideline.

Guideline questions:

- Should a restricting eligibility span be placed in `gold_evidence` when it supports a negative answer for the gold profile, or in `inapplicable_evidence` because the advertised program itself does not apply? This batch follows the same negative-support treatment used for T14-027.

## Batch 03

Hard cases:

- T14-086 says the student was accepted, but the fixed input `gold_profile` says `academic_status: applicant`; as in Batch 01, the conflicting stated status is omitted and documented in the row.
- T14-093 says coursework is finished and the student is writing a thesis, while the fixed input profile says `academic_status: enrolled`. The answer uses the matching advisor-form evidence, but the conflicting stated status is omitted for validation.
- T14-078 and T14-113 ask about immigration steps not covered by the snapshot. They are `external_only` rather than being filled from general immigration knowledge.
- T14-101 asks about returning in spring 2027, but the snapshot contains a 2026 return guide only. It is labeled unanswerable, with the 2026 guide recorded as outdated evidence.
- T14-092 is partial because the career program is restricted to specified science-and-technology institutions and visa-track universities, while the evidence does not establish Hanyang's inclusion.
- T14-114 does not use `condition_sets`: the ERICA HIEA notice gives IELTS/TOEFL as the English-track substitute in parentheses, not as source-level “or” branches in the required format.

Guideline questions:

- For future-term procedural questions such as T14-101, should the latest prior-year guide always be recorded as `outdated_evidence`, even when its process may later be reused unchanged?
