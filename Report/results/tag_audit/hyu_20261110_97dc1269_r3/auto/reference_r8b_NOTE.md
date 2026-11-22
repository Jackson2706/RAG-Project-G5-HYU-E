# T10e reference re-check under audit rule 8b

This is an automated audit. The reference annotator, Codex, also wrote the tagging rules, and the audit is not human-validated.

The pass changed 50 of 150 rows. Only `academic_status`, its `evidence` entry, and the appended `notes` marker changed; no `audience` or `any_of` value needed revision.

| Old value | New value | Rows |
|---|---|---:|
| `enrolled` | empty | 35 |
| empty | `applicant` | 9 |
| empty | `leave_of_absence` | 5 |
| empty | `admitted_not_enrolled` | 1 |

Examples:

- `0089f417-c00e-50d3-b644-fa9409e8400c`: “For 25-2 Freshmen” identifies an audience and year, not a stated academic status, so `enrolled` was removed.
- `43605a3b-1554-5c46-84fc-dddcec014072`: “Undergraduate & Graduate school students cannot apply for HIEA when taking other scholarships” is scholarship eligibility for current students, not stated enrollment, so `enrolled` was removed.
- `bd4dedb6-3a1b-5b99-a28a-38a14763fbd9`: “4. ELIGIBILITY” appears inside the 2026 GKS-G application guide; rule 8 assigns every non-acceptance chunk of that guide to `applicant`.
