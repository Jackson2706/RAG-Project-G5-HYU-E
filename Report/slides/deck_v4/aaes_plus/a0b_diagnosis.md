# Why A0b (AAES spec-fixed) kept 0 of the 7 useful dev questions

Source: `a0b_diagnosis.json` (`Sources/scripts/deck_v4_a0b_diagnosis.py`, dev only, run 2026-11-16, index r5, stops
after evidence sufficiency). The 7 dev cases are those labelled conditional_answer or clarify.

| Case | Labelled detail | A0 | A0b | What removed the split in A0b |
|---|---|---|---|---|
| T14-017 | campus | CLARIFY (different procedures) | ANSWER | 3 extractions: 2 came back NONE, 1 answered. NONE was dropped, so only one distinct answer was left: "same answer" |
| T14-032 | campus | CLARIFY (many branches) | ABSTAIN | campus rule: no campus-scoped chunk for both campuses, so campus was not a candidate; the yes/no check then said "no" |
| T14-044 | campus | CLARIFY (different procedures) | ANSWER | campus rule: campus dropped, no other branch left |
| T14-120 | campus | CLARIFY (many branches) | ABSTAIN | campus rule, then the yes/no check said "no" |
| T14-132 | campus, academic status | CONDITIONAL | ANSWER | campus rule; the remaining academic-status split had one evidence set, so one answer |
| T14-130 | visa, degree, year, TOPIK, track | ANSWER | ANSWER | A0 itself found no branch (nothing for A0b to keep) |
| T14-209 | Korean standard | ABSTAIN | ABSTAIN | A0 itself found no applicable evidence |

**Cause.** A0 found the split in 5 of the 7. A0b lost all 5 to two of its three changes:
1. **The campus rule (4 of 5):** the campus may branch only when the support holds a chunk scoped to Seoul alone and
   another scoped to ERICA alone. In these cases only one campus's pages are in the top-3 evidence. That is exactly
   when the answer depends on the campus (the other campus has no page, or its page was not retrieved).
2. **NONE answers (1 of 5):** a branch whose extraction said NONE was dropped, so a split with one answer and two
   NONEs became "the same answer".
The yes/no check before asking turned 2 of the 4 campus-rule cases into ABSTAIN.

**Consequence for AAES+ "both" at step 3.** It keeps the campus as a candidate (no campus rule) and has no yes/no
check. A NONE extraction is read as "that group is referred", which is still a split, so the rules' decision stays.
It changes the rules' split only when every evidence set answered and all answers are the same (then ANSWER).
