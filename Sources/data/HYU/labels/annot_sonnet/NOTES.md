# Sonnet annotation notes (T15c, GUIDELINES v1.2)

Annotator: claude-code:claude-sonnet-5-5. Batches done are listed per section; a batch is "done" only after validation exit 0.

## Batch 04 - done (30 rows, validation exit 0)

Hard cases
- T14-115, 119, 120, 128, 133, 134, 136, 138, 139, 140, 148: campus unstated and only one campus has evidence (open question 10.4.1). I follow the gold persona's campus: ERICA evidence is gold, other-campus evidence is inapplicable. T14-115 (ERICA admitted, Korean standard fail) is partial only because of the ERICA return-to-school guide; Seoul has the real acceptance guideline.
- T14-116, 132: campus unstated and both campuses have different university-insurance evidence, so campus is a branch (8.3, two branches, conditional_answer). The other campus's spans are listed under inapplicable_evidence.
- T14-117, 121, 124, 130: part-time hours. Seoul-hosted permit form (20/25/30 h, language training 20 h) conflicts with the ERICA tables (10/30, 15/35) (open 10.4.4). Persona campus wins; the form is used only where ERICA has no row (T14-117, language training).
- T14-126: question implies the student is not yet on D-10; gold_profile visa changed D-10 to D-2 (9.5). T14-126, 133, 134: "when/whether before graduation" is not in the snapshot, labelled partial (borderline vs unanswerable, 10.4.3).
- T14-130: all attributes unstated (visa, degree level, topik) plus a source conflict: clarify.
- T14-138: "which guide is current": snapshot only has the download link page and a 2021 guideline; labelled answerable, borderline partial.
- T14-148, 153: no 2026-2 notice in the snapshot (latest is 2026-1 / March 2026): unanswerable under 10.1.

Guideline questions
- For conditional_answer, are the enumerated other-branch passages gold or inapplicable? I used gold for year/degree/TOPIK branches only when the persona's own row is in gold; other-campus branch spans go to inapplicable.
- Is "which notice is current this semester" a time-specific fact (unanswerable) when only the previous term's notice exists? I treated it as yes.

## Batch 05 - done (30 rows, validation exit 0)

Hard cases
- Personal status lookups and action requests (T14-165, 176, 181, 182, 187, 188, 192): labelled unanswerable, not external_only, because no snapshot page points to another source for that specific information. A generic HiKorea/1345 contact block was not counted as a referral (open question 10.4.2). T14-170 (book a Seoul Immigration Office appointment) is external_only because the 2026-1 re-registration guide explicitly gives 1345 / HiKorea for visiting the office.
- T14-155 external_only: the ERICA dormitory pages themselves send readers to the dormitory site notices; the only notice in the snapshot is from 2025 spring.
- T14-156: only an August 2025 ERICA group visa notice (content in attachments); labelled unanswerable on currentness (borderline partial).
- T14-158: referent "which career event is newer" is ambiguous (10.4.5); I compared the graduate-only Global Career Start program (posted Oct 2025) with the 2025 Job Fair (posted Sep 2025, held Nov 20, 2025).
- T14-174, 175, 180: NHI exemption / leave / dispute questions, 2025 notice only has the premium: unanswerable (T14-174 is borderline partial because the 2021 notice says NHI is mandatory).
- T14-186: partial; the 2021 notice gives phone numbers but the receipt steps are in an attachment with no text.
- T14-173, 190: the 2023 Global Talent Fair page has only a title; unanswerable (not unanswerable_unreadable since it is not known to be a .hwp/scan).

Guideline questions
- Should a title-only page whose details are probably in an image count as unanswerable_unreadable?
- Same as batch 04: "latest notice is from the previous term" treated as time-specific, not supported.
