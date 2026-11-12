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
