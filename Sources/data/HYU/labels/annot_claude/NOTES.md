# T16 Claude Code blind annotation notes (GUIDELINES v1.1)

Annotator: `claude-code:claude-opus-5-5`. Rows have `case_version` "1.1" and snapshot `hyu-20261110-97dc1269`.
Part 1 was relabelled from scratch; the old part 1 file and old notes were overwritten without being read.

## Part 1 (`part_1.jsonl`, 29 cases): done

`python -m labeling.validate data/HYU/labels/annot_claude/part_1.jsonl --annotation` exits 0.

Hard cases:
- T14-017, T14-018, T14-026, T14-032, T14-044: the campus is not stated and the Seoul and ERICA routes, dates or
  contacts differ, so these are `conditional_answer` on `campus` (8.3). The gold profile is Seoul, so the ERICA spans
  are inapplicable.
- T14-026: "international student group" is read as the OIA ambassador group (Global Love Hanyang / GLOBAL LOVE HYU).
  The 2026 notice has a Korean title and contains only a form link, so the stable rules come from the 2025 English notice.
- T14-102: no page says outright that students on leave cannot extend their residence card. The answer combines the
  rule that students on leave must leave Korea within 30 days (ERICA leave guide) with the extension document list.
- T14-109: "Do visiting students have to join NHI?" No page names visiting students or a minimum stay, so I labelled
  it `partial`. It could also be read as answerable.
- T14-113: newly admitted student, campus not stated, ERICA persona. The Seoul CoA steps are campus-specific; I
  treated the D-2 visa documents as national. ERICA's CoA steps are not in the English text, so `partial`.
- T14-114: the HIEA language condition is met through `condition_sets` (TOPIK or English track). `academic_status`
  (newly admitted vs enrolled) changes eligibility, so it is the branch.
- T14-078: `external_only`, because the ERICA NHI page sends all NHI questions to NHIS (9.2).

v1.1 questions:
- 9.3 vs 3.4: for a stated campus with no own-campus evidence the answer is `abstain`. When the campus is unstated
  and only one campus has evidence (T14-113), is it `clarify` or `partial`/`abstain`?
- Some events are only described in old notices and the question gives no term (T14-046 counseling month, 2021;
  T14-071 trips, 2024). I labelled them `answer` with a date caveat. Does 9.7 require evidence for the current term here?

## Part 2 (`part_2.jsonl`, 25 cases): done

`python -m labeling.validate data/HYU/labels/annot_claude/part_2.jsonl --annotation` exits 0.

Hard cases:
- T14-130 "Can I work part time here?": nothing is stated, and visa, degree, year and language all matter, so
  `clarify`. The Seoul part-time confirmation form (45669e0e, 2025-10) gives 20/25/30 hours per week, which conflicts
  with the ERICA visa table (10/30 and 15/35). This needs adjudication. T14-214 keeps the hours out of the required facts.
- T14-158 "Which ERICA career event is newer": unclear whether this means posting date or event date, and which events
  are being compared. The answer names Global Career Start (2025-10) over the 2025 Job Fair (2025-09), plus the newest
  board event, the Hyundai E&C popup (2026-03).
- T14-139 / T14-221 (9.5 updates): "I start this fall" means the persona is no longer an applicant, so academic_status
  becomes `admitted_not_enrolled`. "I passed the university Korean test now" changes korean_standard from `fail` to
  `pass`. Both are noted in the rows.
- T14-175: the 2025 NHI notice has an unreadable `.hwp` attachment (Seoul foreigner service centre guide). It might
  hold the answer, which would make the case `unanswerable_unreadable` instead of `external_only`.
- T14-195 / T14-230: one required fact can never have a span (a guaranteed approval; the exact D-10 timing), so
  `partial` -> `abstain`.

v1.1 questions:
- The validator's stale-profile exception needs `slice == multi_session`, but annotator files have no slice. Any
  stated update in a multi-session case must therefore be copied into `gold_profile` (done for T14-221).
- NHI questions the snapshot cannot answer (T14-078, T14-136, T14-174, T14-175): I chose `external_only` because of the
  ERICA page's blanket NHIS referral. E9 labels a similar NHI question `unanswerable`. Which rule wins outside 9.7?
- Personal immigration actions and status (T14-170, T14-176, T14-182, T14-187, T14-203): `external_only` with the
  HiKorea / 1345 contact span, by analogy with E2.
- 9.1 says `partial` -> `abstain`. When unstated branches also exist (as in T14-130), should `clarify` come first?
