# Tag audit rules (automated audit, PLAYBOOK A14)

These rules apply to the blind reference annotation of chunk applicability tags, vocabulary **v1**
(`Sources/backend/app/rag/applicability.py`). They are given to the reference annotator (Codex)
and to the disagreement reviewer.

**Limitation (state it in every report):** this is an automated audit. The reference annotator,
Codex, also wrote the tagging rules, and the audit is not human-validated.

## What you see, and what you write

You see each chunk's text, its heading path, its document title, the site (`seoul` or `erica`) and
the post date. You never see the system's predicted tags. For each chunk, write which students it
applies to, using only the v1 vocabulary.

## Rules

1. **Judge only from the chunk text and the heading path** (the title counts as part of the
   heading path).
   - Do not use other chunks, outside knowledge, or what the page "usually" says.
2. **A value needs textual support.** Quote the supporting words for every value in `evidence`.
   - Campus is the only exception: it may come from the site (`seoul` → `["seoul"]`, `erica` →
     `["erica"]`).
3. **Thresholds cover the full range.**
   - "TOPIK 3 or above", "level 4 or higher", "Lv4~6" and "5+" mean every level from N up to 6.
   - "below level 3" or "not met (X)" means `none` up to N−1.
   - "Year 1-2" means `["1", "2"]`. "Master's/Doctoral" means both. "Graduate" means `master` and
     `doctoral`.
4. **A chunk about several groups lists all of them.** Example: a table chunk with rows for
   bachelor's AND master's students gets `degree_level: ["undergraduate", "master"]`. Record in
   `topik_scope` whether a TOPIK condition covers the whole chunk (`whole_chunk`) or only one line
   or row of it (`one_line`).
5. **Alternatives joined by "or" are condition sets.** "valid TOPIK certificate or IELTS/TOEFL (for
   English track)" gives `any_of: [{"topik_level": ["1","2","3","4","5","6"]}, {"english_track": ["yes"]}]`.
   - Put those attributes in `any_of`, not in `constraints`.
   - Use `any_of` only when the text itself says "or".
   - **5b.** If only ONE of the alternatives is in the vocabulary, e.g. "TOPIK 4 or higher, or the
     Social Integration Program, or IIE level 4", that attribute is **not a constraint**: a student
     can qualify without it. Write no `constraints` and no `any_of` for it, and record the whole
     alternative in `out_of_vocabulary_condition`. (Added 2026-11-11, after the reference pass:
     4 rows had a one-set `any_of`. They were normalized this way in `reference_normalized.jsonl`,
     and the original is kept.)
6. **Conditions outside the vocabulary are not misses.** Examples: GPA, nationality, attendance,
   money amounts, documents.
   - Record them in `out_of_vocabulary_condition` as short text.
   - Never force them into a vocabulary attribute.
7. **Preferences are not conditions.** "preferred", "additional points", "bonus", "advantage" and
   "optional" never give a constraint. Record them as out-of-vocabulary text with a `preference:`
   prefix.
8. **Applicant rules:**
   - A chunk of an admission guide (undergraduate or graduate admission, GKS application
     guidelines, student recruitment) that addresses prospective students gets
     `academic_status: ["applicant"]` and `audience: applicant`.
   - Acceptance guides for admitted students get `admitted_not_enrolled` and `audience: admitted`.
   - Scholarship "applicants" who are already students are `audience: enrolled`, NOT `applicant`.
9. **`korean_standard`** (`pass` / `exempt` / `fail`) only when the text names the Korean-language
   admission standard: "satisfied / exempted from / did not satisfy the Korean Language Standards".
   A TOPIK level is `topik_level`, not `korean_standard`.
10. **`scope: national`** needs both of these:
    - a national rule: immigration or visa law (alien registration, residence extension, status
      change, part-time work permits) or National Health Insurance;
    - no campus-specific procedure in the chunk, such as "submit to OIA" or "apply on HY-in".

    Otherwise use `scope: campus`. A national chunk gets `campus: ["seoul", "erica"]`.
11. **`effective_term`** (`YYYY-1` / `YYYY-2`):
    - A term named in the text wins ("2026 Fall Semester" → `2026-2`).
    - Otherwise use the post date: January–June → `-1`, July–December → `-2`.
    - Undated pages get `null`.
12. **If nothing applies to a specific group, write empty `constraints` and `any_of`.** That is a
    valid answer: "unconditioned". Do not guess.

## Output format (one JSON object per line)

```json
{"chunk_id": "…", "constraints": {"degree_level": ["undergraduate"]}, "any_of": [],
 "scope": "campus", "campus": ["seoul"], "effective_term": "2026-1",
 "evidence": {"degree_level": "Undergraduate students"}, "topik_scope": null,
 "audience": "enrolled", "out_of_vocabulary_condition": "GPA ≥ 3.0", "notes": ""}
```

`topik_scope` is `whole_chunk`, `one_line` or `null`. `audience` is `applicant`, `admitted`,
`enrolled`, several joined with `|`, or `null`.

## Disagreement review (second pass)

You see the chunk, the predicted value and the reference value for each disagreeing attribute. You
do not know which side came from the system. Decide with the rules above: `a`, `b`, `both_wrong`
(then give the correct values) or `ambiguous`. Give a one-line reason that quotes the text.
