# Case cards (A35 Step 2)

Replies are copied from the saved runs and only shortened with "…": test-1 from
`Report/results/test-final/raw/` (qualitative only), dev from `Report/results/dev-03/raw/`. Labels and evidence come
from the frozen label files through `Sources/scripts/export_case_cards.py` (it reads labels with the runner's
reader; nothing was re-run). Labels are LLM-annotated (A33). Action labels are evaluator v2.

## Counts for the same slides (test-1, evaluator v2, `Report/results/test-final/hyu_test_v2_per_case.csv`)

| Cases | A0 acceptable, B0 not | B0 acceptable, A0 not |
|---|---|---|
| The answer depends on the student (15 cases labelled conditional answer or clarify) | 10 | 0 |
| The sources do not answer (46 cases labelled abstain) | 1 | 30 |

## Where AAES helps (test-1)

### T14-088 "How many hours can an international student work part time?"

- **Evidence.** The ERICA visa page has a table: bachelor's years 1-2 with Korean level 3 may work 30 h on weekdays
  (10 h without it); years 3-4 need level 4; master's/doctoral 35 h with level 4, 15 h without. A work permit is
  needed in every case.
- **B0** (answer): "The number of allowed part-time work hours depends on the student's status and Korean language
  proficiency: … **Undergraduate students:** 20 hours per week (if TOPIK Level 3) or limited to 10 hours per week …
  **Masters/Doctoral degree students:** 30 hours per week (if TOPIK Level 4 or higher) or limited to 15 hours per
  week …" These are the Seoul guide's figures, stated for everyone; for an ERICA student the weekday limits are 30
  and 35 h.
- **A0** (clarify): "The answer depends on your degree level. Which applies to you: undergraduate, master, doctoral,
  language program or non degree?"
- **Label.** clarify (conditional answer also accepted); branches: degree level, year, TOPIK level.

### T14-051 "How do I sign up for the university group insurance?"

- **Evidence.** ERICA: the premium is a separate item on the tuition bill and is paid with tuition; returning or
  completed students in Korea subscribe individually on the insurer's website. Seoul: for enrolled students the
  premiums are paid in full from the university's budget.
- **B0** (answer): "To sign up for the university group insurance, students must pay their insurance premium as a
  lump sum when paying for their tuition. [E3] Returning students … must subscribe to the insurance individually
  through the insurance company's website. [E3]" This is the ERICA procedure, given to every student.
- **A0** (clarify): "The answer depends on your campus. Which applies to you: Seoul or ERICA?"
- **Label.** clarify; branches: campus, academic status.

### T14-155 "I'm moving into the ERICA dorm this semester. Which dorm notice is current?"

- **Evidence.** The only ERICA dormitory notice in the snapshot is an old application round; the ERICA dormitory
  page says to check the notices on each dormitory's website.
- **B0** (answer): "The current dorm notice for the ERICA campus is found in **Evidence [E1]** and **[E2]** … the
  2021 application period (Jan 25th - Feb 3rd) …" It presents a 2021 notice as current.
- **A0** (abstain): "The official pages I found do not apply to you (they are for another campus or student group).
  Please contact the ERICA campus OIA office."
- **Label.** abstain. A0 takes the right action, but its template gives the wrong reason (the pages are ERICA pages
  that are out of date) and it does not point to the dormitory website.

## Live demo (dev)

### T14-132 "Which insurance rules apply to me?" (compare B0 | R16 | A0; Execution tab on A0)

- **Evidence.** ERICA: university group insurance KRW 25,000 on the tuition bill, plus National Health Insurance at
  50% of the resident premium. Seoul: premiums for enrolled students are paid from the university's budget.
- **B0** (answer): "The following insurance rules apply to you based on your status and travel plans: …
  **Travel Duration:** If you leave the country for 1 month or more, your insurance premiums are waived … " It
  lists rules from one page with no campus condition.
- **A0** (conditional answer): "If you are at the Seoul campus with an admitted, enrolled, leave of absence,
  completed coursework, or graduating status, you should ask the OIA office for specific rules. … If you are at
  the ERICA campus with a leave of absence status, international students must register for group insurance … [E1]"
  It states the right conditions (campus, then status); the Seoul branch had no applicable chunk, so it refers.
- **Label.** clarify (conditional answer also accepted); branches: campus, academic status.

### T14-120 "Does my insurance change after my visa switches from D-4 to D-2?"

- **Evidence.** ERICA: degree students pay the KRW 25,000 group insurance on the tuition bill; students in language
  courses ask their language school; National Health Insurance applies to international students.
- **B0** (abstain under v2): it misses the split that the evidence does contain: "The provided evidence does not contain information
  regarding how a student's insurance status changes specifically when their visa switches from D-4 to D-2."
- **A0** (clarify): "The answer depends on your degree level. Which applies to you: undergraduate, master, doctoral,
  language program or non degree?" The evidence splits exactly on degree course vs language course.
- **Label.** conditional answer (clarify also accepted); the label's branch attribute is campus, and the gold
  evidence splits on language course vs degree course.

## Counter-example (dev)

### T14-042 "Is there a winter school for international students?"

- **Evidence.** The Seoul International Winter School page: 130+ English-taught courses, cultural activities, two
  two-week sessions.
- **B0** (answer): "Yes, Hanyang University offers International Summer/Winter schools as part of its
  degree-seeking student programs for international students [E2]."
- **A0** (clarify): "The answer depends on your campus. Which applies to you: Seoul or ERICA?" There is one winter
  school and one answer; the question is unnecessary.
- **Label.** answer.

## Dropped cases

- **T14-121** (test-1, "How many hours can I work with a D-2 visa?"): B0 is wrong ("A D-2 visa does not allow
  part-time work"), but A0's conditional answer does not state the right conditions. It gives 10 hours to
  "undergraduate or doctoral degree-seeking student[s] in a language program" and "ask the OIA office" for the rest,
  while the gold evidence gives 30 h with Korean level 3 and 10 h without.
- **T14-114** (test-1, ERICA scholarship with TOPIK 1 on the English track): B0 declines instead of committing to an
  answer, and A0's conditional answer covers only the TOPIK scholarship, not the English-track route with IELTS or
  TOEFL that the question asks about.
- **T14-044** (dev, "How can I reach the international office?"): B0 gives both the Seoul and the Ansan address, so it
  is not wrong for either campus.
