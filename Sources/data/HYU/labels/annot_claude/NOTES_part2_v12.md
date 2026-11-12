# T16 part 2: notes for the v1.2 re-label

Annotator: claude-code:claude-opus-5-5. Rulebook: GUIDELINES.md v1.2 (section 10 wins over 9, and 9 over 1-8).
Input: `annotation_input/t16_part2.jsonl` (25 cases). Output: `annot_claude/part_2.jsonl`. I overwrote it without reading the old file.

Status: **done**, 25 rows. `python -m labeling.validate data/HYU/labels/annot_claude/part_2.jsonl --annotation` exits 0.
Blind: I did not open annot_codex/, annot_sonnet/, drafts/, personas.json, the old part_1/part_2 or NOTES.md.

## gold_profile updates (9.5)
- T14-139: the question says "I start this fall", so academic_status changes from applicant to admitted_not_enrolled.
- T14-221: the question says "I passed the university Korean test now" (the history said the standard was not met), so korean_standard changes from fail to pass.

## Hard cases and how I decided them
- **T14-130** (10.4.3 / 10.4.4). Nothing is stated, and the eligibility evidence splits on visa (D-2-8 six-month rule, D-2-5 excluded) and on language (TOPIK or English track). That is more than 2 branches, so `clarify` on visa. I treated eligibility as a national rule from the ERICA Visa page and did not make campus a branch. The Seoul confirmation form (20/25/30 h) and the ERICA table (10/30, 15/35) conflict on hours, but the question asks "can I", not "how many hours", so hours are not a required fact.
- **T14-170, 176, 182, 187** (10.4.2). These are personal immigration actions or status checks. I counted the Korea Immigration Service contact block (HiKorea website, 1345) as "refers elsewhere", which gives `external_only`. For 170 the referral is explicit ("visit Hi Korea to book their application appointment", as in E2). For the three re-entry cases it is only the generic contact block, so `unanswerable` is the alternative there.
- **T14-203** (an action request, like 170): the snapshot fully supports the self-service address-change procedure (14 days, HiKorea or a local office, the documents). I labeled it `answerable` and `answer`, not `external_only`.
- **T14-208**: the Seoul undergraduate application language documents are not in the snapshot text. The admission page only links an "Undergraduate Admission Guide Download", and I read that link as a referral, so `external_only`. It is arguable as `unanswerable`, because the guide is on the same site.
- **T14-136, 174, 175**: no required fact is supported, and the NHI pages refer all inquiries to the NHI Service (1577-1000), so `external_only` (10.3.2).
- **T14-139, 154** (10.4.1): the campus is unstated and only Seoul has orientation materials. The evidence does not split on campus (10.2), so `answer`. The 2026 spring and 2025 fall materials go to outdated_evidence.
- **T14-120**: insurance differs by campus (ERICA KRW 25,000 on the tuition bill; Seoul paid by the university), so this is a 2-branch `conditional_answer`. The language-school sentence exists only on the ERICA page (10.4.1).
- **T14-132**: three or more attributes split the answer (campus, academic_status, student_type), so `clarify` on campus.
- **T14-158** (10.4.5): "newer" could mean post date or event date. I used post date: Global Career Start, posted 2025-10-28, is newer than the 2025 Job Fair, posted 2025-09-10. Both events have passed.
- **T14-184** (10.4.5): the referent is ambiguous (an outbound partner visit, or Hanyang's own visiting program). Nothing says "fully in English", so `unanswerable`.
- **T14-195, T14-230**: some facts are supported (the requirements, or the D-10 eligibility and documents) and one is not (the approval guarantee, or when to apply). Both are `partial` and `abstain`. In 230 the extension-of-stay "4 months before expiry" rule is inapplicable.
- **T14-221**: only Seoul has acceptance guidelines. Section 3 rule 4 says never to answer from the other campus, so `abstain`.
- **T14-190**: the only match is a Seoul 2023 notice whose text is just its title. `unanswerable`.

## Guideline questions
1. 10.4.2 should be decided explicitly. Does the generic HiKorea/1345 contact block count as a referral for personal immigration actions? It affects 3 rows here, and 4 more if 170 is included.
2. An action request whose procedure is fully documented (T14-203): is `answer` intended? The validator has no "cannot perform action" fact.
3. An attachment link with no extracted text (T14-208, the admission guide download): is it a referral (`external_only`) or `unanswerable`?
4. The clarify question has no field of its own. I put it in `reference_answer` and `notes`.
