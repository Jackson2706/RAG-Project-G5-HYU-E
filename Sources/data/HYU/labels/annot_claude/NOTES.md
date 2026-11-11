# Claude Code annotation notes (T16, part 1)

Annotator: `claude-code:claude-opus-5-5`. Blind: only GUIDELINES.md, questions.jsonl, the T16 part-1
input file, the snapshot (via `labeling.search` and exact slices), and `labeling/validate.py` were read.

File: `part_1.jsonl`, 29 rows, `python -m labeling.validate ... --annotation` passes with no output.

## Hard cases

- **T14-026** ("apply to the international student group"): the snapshot has no clear referent. The
  candidates were Global Sarang Handae (Korean title, current Seoul undergraduates only), ISF Korean
  class and ERICA Hanmille. Labeled `unanswerable` / `abstain`, with `clarify` acceptable. The question
  wording may need a rewrite.
- **T14-033** (where to apply to return, Seoul): the 2026-1 guide says applications in person or by
  e-mail are not accepted. The step that names HY-in was a screenshot and was lost in parsing. The
  explicit "apply only through HY-In portal" line is in the 2021-2 guide. I put that old span in
  `gold_evidence`, not in `outdated_evidence`, because it is the only explicit source.
- **T14-035 / T14-102** (extending the residence card; gold persona is on leave): the "must leave Korea
  within 30 days, return the RC" rule appears only in the ERICA leave-of-absence guidelines. I treated
  it as national, because it is driven by immigration reporting, and used it for a Seoul persona.
  T14-035 does not state the leave status, so it gets `conditional_answer` on `academic_status`. T14-102
  states it and gets `answer`, with `partial` because no page literally says "cannot extend while on leave".
- **T14-046** (counseling month): the only edition is from December 2021 and is for graduate students.
  The gold persona is non-degree. Labeled `partial` / `answer` with an "as of" caveat and an
  eligibility caveat.
- **T14-081 / T14-084** (admission language requirement by track): the Undergraduate Admission Guide page
  has only download links and no text. The 2026 acceptance guideline names a "Korean standard pass or
  exemption" group but does not say who is exempt. Both labeled `partial` / `abstain`. In T14-084,
  "apply" could also mean HIEA, where English-track students may substitute IELTS/TOEFL, so `clarify`
  is acceptable.
- **T14-113** (newly admitted ERICA student, visa): no readable English ERICA guide. The group visa
  notice text is only "read the attached guides". The Seoul CoA and Korean-standard-fail rules went to
  `inapplicable_evidence`. Note that the persona's gold profile has `visa: D-2` and
  `korean_standard: fail`, a combination that Seoul's rules forbid. That is a persona-consistency
  question for the adjudicator.
- **T14-078** (NHI after graduation): labeled `external_only` rather than `unanswerable`, because the
  ERICA page sends all NHI questions to NHIS (1577-1000).
- **T14-114** (ERICA scholarship with TOPIK 1, English track): `condition_sets` is TOPIK or English
  track, and both sets fit. The gold persona is `admitted_not_enrolled` and HIEA needs grades from the
  previous semester, so `academic_status` is a branch.

## Guideline questions

1. **May evidence from one campus be used for the other when the rule looks immigration-driven but is
   published only by one campus** (ERICA's 30-day departure on leave, ERICA's NHI waiver for ≥1 month
   abroad)? Section 5 lists immigration and NHI as national. I followed that, but a sentence on
   "national rule found only on one campus's page" would help.
2. **When the newest version is missing a detail that an older version states** (T14-033), should the
   older span go to `gold_evidence` or to `outdated_evidence`? Section 3's temporal rule covers only
   "only an old version exists".
3. **Do semester vs holiday hours** (library, T14-058) **count as a branch?** `term` is not in
   vocabulary v1, so I listed both in the answer and gave no branch.
4. **Unstated `degree_level` in eligibility-limited programs** (KIRD counseling: graduate students
   only, T14-015; Counseling Month: graduate only, T14-046): branch or caveat? I chose caveat in both,
   because the question framing ("researchers", "what happens") does not ask about eligibility.
5. **Implied but unspoken status** ("after I graduate", T14-078): I did not put
   `academic_status: graduating` in `stated_profile`, following "never infer". Please confirm.
6. **Outside-vocabulary deciders** (partner-university nomination for exchange vs visiting, T14-107;
   arts vs non-arts program for the ERICA TOPIK scholarship, T14-114) are written as caveats. These may
   be candidates for vocabulary v2.
