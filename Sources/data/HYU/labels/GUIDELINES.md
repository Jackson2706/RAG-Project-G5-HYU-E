# HYU Compass labeling guideline (v1.2)

Status: **v1.0 approved at Gate G3 (2026-11-11, PLAYBOOK A22); v1.1 amendment (section 9, 2026-11-12, A30) and v1.2 amendment (section 10, A31) win where they differ; section 10 wins over section 9.** Written with applicability vocabulary **v1**
(`Sources/backend/app/rag/applicability.py`; PLAYBOOK A17). G2a is passed (A20); G3 approved this guideline.

**Vocabulary v1 in short** (values are in `applicability.py`; never copy them):
- `campus`, `degree_level`, `year`, `student_type` (no `short_term`), `visa`, `topik_level`,
  `english_track`, `korean_standard` (`pass` / `exempt` / `fail`: the admission Korean-language
  standard, a pass/fail result, not a TOPIK level);
- `academic_status` with `applicant` first. `applicant` means a prospective student before
  admission.
- **Scope default:** unless the student says they are applying, assume they are **not** an
  applicant. Write `academic_status: applicant` in `stated_profile` only when the student says so.

Snapshot: `hyu-20261110-97dc1269`. Evidence spans point into this snapshot's `documents.jsonl`.
Find spans with `python -m labeling.search` (T12).

## 1. What a case is

A case is one student question, optionally with an earlier session. It also says what a good
assistant should do, based only on the official English HYU pages in the snapshot.

We label two different things. Keep them apart:
- **Relevance:** does a passage talk about the topic of the question?
- **Eligibility (applicability):** does the passage apply to *this* student?

A passage can be relevant and still not apply. Example: the master's row of a work-hours table,
when an undergraduate asks.

## 2. Fields

The schema is in PLAYBOOK Appendix D; `labeling/validate.py` checks it. These are the fields that
need judgement.

| Field | What to write |
|---|---|
| `question` | One realistic question, as a new international student would type it. English. |
| `session_history` | Only for `multi_session`. These are earlier turns that state profile facts. |
| `stated_profile` | Only the attributes the student actually said, in this question or the history. Use vocabulary values. Never infer. |
| `gold_profile` | The full persona, from T13 `personas.json`. The system never sees it. It contains `academic_status: applicant` **only** when the persona is a prospective student (the scope default). |
| `branch_attributes` | Vocabulary attributes whose value changes the correct answer for this question, given the evidence. Empty if nothing changes it. |
| `condition_sets` | Optional. Use it when the evidence says one requirement can be met in alternative ways joined by "or", e.g. `[{"topik_level": ["1","2","3","4","5","6"]}, {"english_track": ["yes"]}]` (a valid TOPIK certificate **or**, for English-track students, IELTS/TOEFL). The student qualifies if **any** set fits. Only use it when the text itself says "or". |
| `answerability` | `answerable`, `partial`, `unanswerable`, `external_only` (the answer is only on another site, such as HiKorea), `korean_only` (the answer exists only in Korean), or `unanswerable_unreadable` (only in a `.hwp` file or a scanned PDF; PLAYBOOK A4). |
| `expected_behavior` | The single best behaviour; see section 3. |
| `acceptable_behaviors` | Every behaviour that would also be fine. It always includes `expected_behavior`. |
| `required_facts` | 1–4 short facts a correct answer must contain. Conditions count as facts, e.g. "depends on TOPIK level". |
| `gold_evidence` | Snapshot spans that support the answer **for the gold profile**, each with `applies_to_gold_profile: true`. |
| `inapplicable_evidence` | Relevant spans that do NOT apply to the gold profile, with `why` (for example "master's row", "Seoul procedure for an ERICA student"). |
| `outdated_evidence` | Relevant spans from a superseded or older version, with the newer one in `gold_evidence`. |
| `condition_scope` | `national` if the rule is national law or policy (immigration, NHI), else `campus`. |
| `reference_answer` | 1–4 sentences, written for the gold profile, citing the facts in `required_facts`. |

Attributes **outside the vocabulary** are not branch attributes: GPA, attendance, nationality. A
good answer states them as caveats ("you also need a GPA of at least
2.0"). The assistant never asks the student about them. If you think one matters a lot, note it in
`notes` (it feeds vocabulary v1).

## 3. Choosing the expected behaviour

Decide in this order:

1. **Is there official English evidence that answers the question?** If not, choose `abstain`:
   say what is missing and refer the student to the right office. Use the answerability values from
   section 2.
2. **Does the answer differ between values of an attribute the student has NOT stated?** If not,
   choose `answer`. Unstated attributes that do not change the answer do not matter.
3. **If it differs:**
   - Choose `conditional_answer` when the branches are few (at most 3) and each one is short. The
     answer then gives every branch, e.g. "If you are in year 1–2 …; if you are in year 3–4 …".
   - Choose `clarify` when there are more branches, when the branches need very different
     procedures, or when one question removes most of the uncertainty. Ask exactly **one** question,
     about the attribute that splits the evidence the most.
   - For both, list `branch_attributes`, and put the other behaviour in `acceptable_behaviors`
     unless it would clearly be worse.
4. **If the student stated a value that conflicts with all the evidence** (for example a Seoul
   student asking about an ERICA-only scholarship): choose `answer` if evidence for their own
   campus exists. Otherwise choose `abstain` and refer them. Never answer from the other campus's
   rule.

**Temporal rule:** use the newest version that is in force for the asking term. Older versions of
the same notice go to `outdated_evidence`. If only an old version exists and the rule may have
changed, use `answer` with a caveat ("as of 2025-1 …"); never present it as current.

## 4. Worked examples

All examples use real snapshot passages; the doc ids are shortened here. They are illustrations,
not cases: do not copy them into the label files.

### answer

**A1.** *"When do I have to report a change of address after alien registration?"*
- Profile: stated `{campus: erica}`.
- Evidence: ERICA Visa page (`d66aa2f5…`), "Students must apply within 14 days from the date of any
  changes …", followed by "New place of residence".
- This is national immigration law (`condition_scope: national`). No attribute changes it.
- Label: `answer`; required fact "within 14 days of the change".

**A2.** *"What are the opening hours of the Ansan immigration office?"*
- Profile: stated `{campus: erica}`.
- Evidence: the same page, "09:00-18:00 (Lunch Break: 12:00-13:00)".
- Label: `answer`, `campus` scope.

### conditional_answer

**C1.** *"How many hours a week can I work part-time during the semester?"*
- Profile: stated `{campus: erica, degree_level: undergraduate}`; gold adds `year: 2`,
  `topik_level: 3`.
- Evidence: the "Permitted Hours" rows on `d66aa2f5…`. For year 1–2, it is 30 hours if the Korean
  requirement (Level 3) is met, and 10 hours if not. Year 3–4 needs Level 4.
- `branch_attributes: [year, topik_level]`. Four short branches, but the student's year narrows it
  quickly.
- Label (v1.1, section 9.3): four branches is more than 2, so `clarify` ("Which year are you in?"),
  acceptable `[clarify, conditional_answer]`. The master's/doctoral rows go to `inapplicable_evidence`
  ("graduate rows").
- The GPA ≥ 2.0 rule on the same page is a caveat, not a branch.

**C2.** *"Do I have to pay for the university's private insurance?"*
- Profile: stated `{campus: seoul}`; gold `academic_status: completed_coursework`.
- Evidence: Seoul notice `47317421…`. For enrolled students, "Premiums are paid in full through
  Hanyang University's budget". Students who completed coursework "must pay directly the premiun of
  25,000 won".
- `branch_attributes: [academic_status]`, two branches.
- Label: `conditional_answer`, acceptable `[conditional_answer, clarify]`.

**C3.** *"Which acceptance guideline should I follow, and when do I pay tuition?"*
- Profile: stated `{campus: seoul, degree_level: undergraduate, academic_status: admitted_not_enrolled}`;
  gold adds `korean_standard: fail`.
- Evidence: Seoul notice `2751c7a0…` has two guides: "[Korean Standard Pass or Exemption] Acceptance
  Guideline" and "[Korean Standard Fail] Acceptance Guideline". It says to "check the appropriate
  Acceptance Guideline according to the 'Korean Language' result shown on your admission result
  page".
- `branch_attributes: [korean_standard]`, two branches.
- Label: `conditional_answer`, acceptable `[conditional_answer, clarify]`.

### clarify

**Q1.** *"What documents do I need to change my visa?"*
- Profile: stated `{campus: erica}`.
- Evidence: the ERICA Visa page lists different procedures and documents for D-4 → D-2 (attendance
  and bank-balance rules) and for D-2 → D-10-1 (job-seeker points system).
- The branches are long and very different, so `branch_attributes: [visa]`.
- Label: `clarify` ("Which visa do you hold now?"), acceptable `[clarify]`.

**Q2.** *"How many hours can I work?"*
- Profile: nothing stated.
- The answer depends on degree level, year and TOPIK level, which is six rows.
- The most informative single question is the degree level: it separates the 15/35-hour rows from
  the 10/30-hour rows.
- Label: `clarify`, acceptable `[clarify, conditional_answer]`.

### abstain

**N1.** *"What will the ERICA dormitory fee be in 2027?"*
- No snapshot page states 2027 fees.
- Label: `answerability: unanswerable`, `abstain`. Refer the student to the ERICA OIA, and do not
  guess from older fees.

**N2.** *A question whose only source is a Korean-only notice*
- Example: a Seoul re-enrollment notice with a Korean title and body.
- Label: `answerability: korean_only`, `abstain`. Say that the official notice is in Korean and
  refer the student to the Seoul OIA. Do not translate it into an answer.

### alternative condition sets

**S1.** *"Can I apply for the HIEA scholarship? I'm in the English track and I don't have TOPIK."*
- Profile: stated `{campus: seoul, english_track: yes, topik_level: none}`.
- Evidence: Seoul HIEA notice `…1814932` says "Students who have valid TOPIK certificate or
  IELTS/TOEFL iBT(for English track)".
- `condition_sets: [{topik_level: 1–6}, {english_track: yes}]`. The second set fits, so the
  language condition is met. The GPA rule (3.0 undergraduate / 4.2 graduate) is a caveat.
- Label: `answer`, with required facts "IELTS/TOEFL instead of TOPIK" and "GPA ≥ 3.0 last
  semester (undergraduate)".

## 5. National vs campus-scoped conditions

- **National:** immigration rules (alien registration, residence extension, status change,
  part-time work permits) and National Health Insurance. These apply on both campuses, even when
  the page is ERICA's. Example: A1.
- **Campus:** scholarships, insurance run by the university, orientation, dormitories, acceptance
  guides. Example: the ERICA TOPIK scholarship (`1486dc97…`) applies only to "International
  students studying at Hanyang University's ERICA Campus".
  - A Seoul student asking about it gets the Seoul scholarship evidence if it exists. If it does
    not, the label is `abstain` with a referral. The ERICA rows go to `inapplicable_evidence`
    ("ERICA-only").

## 6. Temporal cases

- **Newer version in force.** The NHI premium notice exists for 2025 (`2bdc754f…`, 75,490 →
  76,390 won) and for 2026 (`19fd4a70…`, 76,390 → 79,320 won from March 1, 2026).
  - For a question in 2026-1, `gold_evidence` is the 2026 notice and `outdated_evidence` is the
    2025 one. The required fact is "79,320 won per month".
  - The snapshot does not link these two notices as versions, so check by hand.
- **Superseded.** The 2021 entry-report notice (`d8ebecb7…`) is superseded in the snapshot. Use the
  newer version, and put the old one in `outdated_evidence`.

## 7. Process rules (Appendix D, AGENTS.md, PLAYBOOK A19)

**Personas (T13, 10–12).** Each persona has a full `gold_profile` in v1 values.

- Together the personas cover every attribute: `campus`, `degree_level`, `year`, `student_type`,
  `visa`, `topik_level` / `english_track`, `academic_status` and `korean_standard`.
- Minimums:
  - at least 2 English-track students (`english_track: yes`, low or no TOPIK);
  - at least 2 ERICA students who ask visa questions (D-2, D-4, D-10);
  - at least 1 applicant (`academic_status: applicant`);
  - at least 1 admitted student with `korean_standard: fail`;
  - at least 1 student with completed coursework;
  - at least 1 graduate student.

**Targets: 180 cases, stratified by campus on purpose, not by campus share.** ERICA has 56/362
documents but most of the conditional pages, so it gets about 40% of the cases.

| Slice | Seoul | ERICA | Total | Notes |
|---|---:|---:|---:|---|
| unconditional | 38 | 25 | 63 | single facts and table look-ups |
| conditional | 25 | 20 | 45 | ≥ 1 branch attribute; a mix of stated, unstated and partly stated; ≥ 6 with `condition_sets` (TOPIK or English track) |
| temporal | 13 | 5 | 18 | newest vs older version; NHI 2025/2026; superseded notices |
| negative | 22 | 14 | 36 | unanswerable, external_only (HiKorea etc.), korean_only, and ≥ 4 `unanswerable_unreadable` (answer only in a `.hwp` file or scanned PDF) |
| multi_session | 10 | 8 | 18 | session 1 states attributes; session 2 asks. ≥ 6 include an **update** (stale profile): D-4 → D-2, coursework completed, Korean standard re-taken |
| **total** | **108** | **72** | **180** | dev ≈ 50, test ≈ 130 (frozen by `labeling.freeze`, seed 13, stratified by slice × campus) |

**Roles:**
- Codex annotates all 180 cases (T15, `labels/annot_codex/`).
- Claude Code annotates a blind, stratified ~30% subset of 54 cases (T16, `labels/annot_claude/`)
  without opening Codex's files.
- `python -m labeling.agreement` reports Cohen's κ (answerability, expected_behavior), branch
  Jaccard and span F1, and writes `adjudication.csv`.
- Humans adjudicate every disagreement and verify every test item (`adjudicated_by: human:<initials>`).
  `labeling.freeze` refuses to run otherwise.
- At least 30% of the questions are written or edited by humans. Report the share.

**Other rules:**
- Every row records `annotator` and `origin`.
- Annotate independently, and never look at system outputs or results.
- Demo cases (8–10) are chosen from **dev only, after the freeze**.
- After every labeling session: run `python -m labeling.validate`, then commit and push the label
  files.

## 8. Decisions at G3 (2026-11-11)

1. **Clarify threshold:** kept. Choose `clarify` when there are more than 3 branches, or when the
   branches lead to different procedures (a different office, form or action). With 2–3 branches
   that share a procedure, choose `conditional_answer`.
2. **Applicant scope default:** kept, with one addition. A question that is itself about applying
   for admission ("How do I apply to the graduate school?", "What are the admission requirements?")
   states `applicant`: write it in `stated_profile` as stated by the question. Otherwise, assume
   the student is not an applicant.
3. **A missing campus is an ordinary branch attribute.** When the Seoul and ERICA rules differ and
   the campus is unstated, `campus` is a branch attribute like any other: `conditional_answer` with
   one branch per campus, or `clarify` ("Which campus are you at?") under rule 1. When the rules are
   the same, campus is not a branch.

## 9. Amendment v1.1 (2026-11-12, PLAYBOOK A30)

Decided after the early agreement check (Codex batches 01-03 vs Claude T16 part 1, κ answerability
0.53). Where this section differs from sections 1-8, **this section wins**. Examples use real snapshot
passages; they are illustrations, not cases.

### 9.1 Answerability counts required facts

- `answerable`: **every** required fact has a gold span in the English snapshot.
- `partial`: **at least one, but not all** required facts have a gold span.
- `unanswerable`: **no** required fact has a gold span (and no other negative value fits).
- `partial` → `expected_behavior: abstain`: refer the student and say what is missing.
  `acceptable_behaviors` also includes `answer`, for an answer that gives the supported facts **and**
  names the missing part.

**E1 (partial).** *"When do I have to report a change of address, and how much is the fine if I'm late?"*
(stated `{campus: erica}`)
- `d66aa2f5…` 2209-2680: "Students must apply within 14 days from the date of any changes …";
  2581-2679: "Failure to report … within 14 days … may result in a fine." No page gives the amount.
- Required facts: "within 14 days" (supported), "the fine amount" (not supported) → `partial`,
  `abstain` ("You must report within 14 days; the snapshot does not state the fine amount, so ask the
  ERICA OIA or the immigration office"), acceptable `[abstain, answer]`.

### 9.2 external_only

`external_only` only when the snapshot **itself** sends the reader to another site or office for
this information. Otherwise `unanswerable`.

**E2.** *"How do I book a visit at the Ansan immigration office?"* (stated `{campus: erica}`)
- `d66aa2f5…` 18307-18340 lists "Website http://www.hikorea.go.kr" (with 1345) as the contact for this
  office, and no page gives booking steps → `external_only`, `abstain`, referring to HiKorea / 1345.
- Contrast: *"What is the Ansan immigration office's parking fee?"* No page refers anywhere for it →
  `unanswerable`.

### 9.3 Branch vs caveat

- **Branch:** the *value* of the answer changes with an **unstated vocabulary attribute** →
  `conditional_answer` when there are **at most 2** branches, otherwise `clarify` (this replaces the
  "at most 3" in sections 3 and 8.1). The procedure rule of 8.1 still applies: different procedures
  → `clarify`.
- **Caveat** (`answer` + caveat sentence): a requirement **outside** the vocabulary (GPA, nationality,
  documents, attendance), or a condition that does **not** change the answer's value.
- `applicant` is never a branch unless the student states it (scope default, 8.2).
- Evidence whose condition status is **unknown** (the tags cannot say who it applies to) → caveat,
  never a branch.

**E3 (branch).** C2: Seoul private insurance (`47317421…`). Enrolled: paid by the university;
completed coursework: 25,000 won. `academic_status` unstated and it changes the value, 2 branches →
`conditional_answer`, acceptable `[conditional_answer, clarify]`.
**E4 (branch, > 2).** C1: work hours on `d66aa2f5…` depend on year and TOPIK (four rows) → `clarify`.
**E5 (caveat).** S1 HIEA (`…1814932`): the GPA ≥ 3.0 rule is outside the vocabulary → stated as a
caveat in the answer, never asked.
**E6 (not a branch).** A1: the 14-day address-change rule is the same for every degree level and
year → `answer`, no branch, even though `degree_level` is unstated.

### 9.4 Spans

Gold span = the smallest sentence(s) or table row(s) that support each required fact. Span F1 is
reported in the agreement report but is **not** a gate; humans adjudicate only clear misses.

### 9.5 Question text vs persona

The question (and session history) wins over the persona. If the question states a detail that
conflicts with `gold_profile`, update `gold_profile` with the stated detail and say so in `notes`
("question states X, persona had Y"). Mark the case for deletion in `notes` only if it becomes
nonsense.

**E7.** Persona `academic_status: applicant`, question "I was accepted, when do I pay tuition?" →
`gold_profile.academic_status: admitted_not_enrolled`, `stated_profile` the same, note the conflict.

### 9.6 Gold vs inapplicable evidence

- **Gold:** the correct answer for this student relies on the passage, **including** a passage that
  shows the student is **not** eligible.
- **Inapplicable:** a rule for another group that the correct answer must not use.

**E8.** ERICA undergraduate, year 3, TOPIK 3, asks "Can I work 30 hours?" (C1 page). The year 3-4 row
that requires Level 4 is **gold** (it is why the answer is "no, 10 hours"). The master's/doctoral
rows are **inapplicable** ("graduate rows").

### 9.7 Time-specific facts

- Dates, deadlines, fees, quotas and amounts need evidence **for the asked term**. Prior-term evidence
  goes to `outdated_evidence`; the case is `unanswerable` (or `partial` when other required facts
  are supported); behaviour `abstain`, naming the term that was found ("the snapshot has the 2026
  rate, 79,320 won; the 2027 rate is not published").
- **Stable rules** (procedures, eligibility, required documents) from the latest version count as
  gold unless a newer version supersedes them. This replaces the "answer with a caveat" sentence
  of the section 3 temporal rule for time-specific facts.

**E9.** *"What is the NHI premium in 2027?"* → `19fd4a70…` (2026) in `outdated_evidence`,
`unanswerable`, `abstain`. *"How do I enrol in NHI?"* asked for 2027 → the latest procedure is gold,
`answer`.

## 10. Amendment v1.2 (2026-11-12, PLAYBOOK A31)

Decided after the v1.1 agreement check (6 disagreements on 29 shared cases). Section 10 wins over
section 9 and sections 1-8. The examples show how the rule is applied; the final label of each case
is the human adjudicator's.

### 10.1 No term stated = the current term

- A question that names no term asks about the **current term at the snapshot date** (snapshot
  2026-11-10: the 2026 fall semester, 2026-2; "next semester" = 2027-1).
- **Time-specific facts** (dates, deadlines, fees, quotas, amounts, event schedules) found only in an
  older term's notice → that fact is not supported: `partial` (other facts supported) or
  `unanswerable`, behaviour `abstain`, naming the term found ("the latest notice is from 2021").
  The old notice goes to `outdated_evidence`.
- **Stable rules** (procedures, eligibility, required documents) from the latest version count as
  supported → can be `answerable`.

**Examples.**
- T14-105 *"Can a student on leave still receive an international scholarship?"*: the 2026 HIEA
  guideline and the 2026 TOPIK-scholarship notice exclude students on leave. Eligibility, latest
  version → supported.
- T14-046 *"What happens during international student counseling month?"*: the only notice is from
  2021; the month, sessions and quota are an event schedule → time-specific, not supported for
  2026-2.
- T14-033 *"Where do international students apply to return to the Seoul campus?"*: the 2026-1
  return guide gives the procedure (online, no in-person or e-mail applications) → stable
  procedure, supported. A detail that is only in an image (the exact menu path) is not a required
  fact unless the question asks for it.

### 10.2 A branch needs the evidence to split

An attribute is a branch **only if the gold evidence gives different answers for different values of
it**. Never `clarify` (or branch) on an attribute that the evidence does not split on, or that the
student's stated details already fix. "Different rules might exist somewhere" is not a split.

**Examples.**
- T14-109 *"Do visiting students have to join Korean health insurance?"* (stated
  `student_type: visiting`): the NHI pages give one rule for international students and no
  different answer per visa → `visa` is not a branch; no `clarify` on visa.
- T14-035 *"How do I extend my residence card?"*: `visa` is a branch only if the extension pages give
  different steps for different visas; `academic_status` only if a page gives a different procedure
  for the asker's possible statuses (e.g. on leave). If the evidence gives one procedure, `answer`.

### 10.3 Negative precedence

1. At least one required fact supported → `partial`, even if the corpus points elsewhere for the rest.
2. No required fact supported **and** the corpus refers the reader elsewhere for this information →
   `external_only`.
3. Otherwise → `unanswerable` (or `korean_only` / `unanswerable_unreadable` when they fit).

**Examples.**
- T14-113 *"I just got admitted. How do I apply for my student visa?"*: if the snapshot supports some
  steps (e.g. the D-2 document list or the certificate of admission) → `partial`, even though
  issuance happens at the embassy. `external_only` only if no step is supported.
- T14-026 *"How do I apply to the international student group?"*: if a page supports the
  application steps of a matching group → not `unanswerable`. Only when no fact is supported and no
  page refers elsewhere → `unanswerable`.

### 10.4 Open questions (not decided by v1.2; adjudicated case by case)

1. Campus unstated and only one campus has evidence (T14-113).
2. A generic contact block (HiKorea / 1345) counted as "refers elsewhere" for personal immigration
   actions (T14-170, 176, 182, 187, 203).
3. `partial` and unstated branches together: `clarify` or `abstain` first (T14-130).
4. Official pages that conflict (T14-130: Seoul part-time form 20/25/30 h vs ERICA table 10/30, 15/35).
5. A question whose referent is ambiguous ("the international student group", T14-026).
