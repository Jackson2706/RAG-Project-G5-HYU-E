# HYU Compass labeling guideline (draft v0.1)

Status: **draft for Gate G3.** Written with applicability vocabulary **v0**
(`Sources/backend/app/rag/applicability.py`). It is updated after Gate G2 approves vocabulary v1.
Per PLAYBOOK A11, no labels are produced before v1 is approved.

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
| `gold_profile` | The full persona, from T13 `personas.json`. The system never sees it. |
| `branch_attributes` | Vocabulary attributes whose value changes the correct answer for this question, given the evidence. Empty if nothing changes it. |
| `answerability` | `answerable`, `partial`, `unanswerable`, `external_only` (the answer is only on another site, such as HiKorea), `korean_only` (the answer exists only in Korean), or `unanswerable_unreadable` (only in a `.hwp` file or a scanned PDF; PLAYBOOK A4). |
| `expected_behavior` | The single best behaviour; see section 3. |
| `acceptable_behaviors` | Every behaviour that would also be fine. It always includes `expected_behavior`. |
| `required_facts` | 1–4 short facts a correct answer must contain. Conditions count as facts, e.g. "depends on TOPIK level". |
| `gold_evidence` | Snapshot spans that support the answer **for the gold profile**, each with `applies_to_gold_profile: true`. |
| `inapplicable_evidence` | Relevant spans that do NOT apply to the gold profile, with `why` (for example "master's row", "Seoul procedure for an ERICA student"). |
| `outdated_evidence` | Relevant spans from a superseded or older version, with the newer one in `gold_evidence`. |
| `condition_scope` | `national` if the rule is national law or policy (immigration, NHI), else `campus`. |
| `reference_answer` | 1–4 sentences, written for the gold profile, citing the facts in `required_facts`. |

Attributes **outside the vocabulary** are not branch attributes: GPA, attendance, nationality, a
pass/fail Korean standard. A good answer states them as caveats ("you also need a GPA of at least
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
- Label: `conditional_answer`, acceptable `[conditional_answer, clarify]`. The master's/doctoral
  rows go to `inapplicable_evidence` ("graduate rows").
- The GPA ≥ 2.0 rule on the same page is a caveat, not a branch.

**C2.** *"Do I have to pay for the university's private insurance?"*
- Profile: stated `{campus: seoul}`; gold `academic_status: completed_coursework`.
- Evidence: Seoul notice `47317421…`. For enrolled students, "Premiums are paid in full through
  Hanyang University's budget". Students who completed coursework "must pay directly the premiun of
  25,000 won".
- `branch_attributes: [academic_status]`, two branches.
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

## 7. Process rules (from Appendix D and AGENTS.md)

- Every row records `annotator` (`codex:<model>`, `claude-code:<model>`, `human:<initials>`) and
  `origin` (`human`, `agent_draft_human_edited`, `agent_draft`).
- **Annotate independently:** never open another annotator's file before submitting your own.
  Labeling agents never see system outputs or results.
- **Demo cases** come from the dev split only.
- **Split and slices:** about 180 cases, dev about 50 and test about 130.
  - The slice targets are in Appendix D.
  - Stratify by slice **and by campus, not proportionally** (A4). ERICA has 56 of the 362
    documents but most of the conditional pages. Aim for at least 40% ERICA cases in the
    `conditional` slice.
- At least 30% of the questions are written or edited by humans.
- Cohen's κ (answerability, expected_behavior) is reported before adjudication. Humans adjudicate
  every disagreement and verify every test item.

## 8. Open points for G3 (team decision)

1. **The clarify threshold:** "more than 3 branches, or very different procedures". Is that the
   rule we want?
2. **Out-of-vocabulary conditions:** should a pass/fail Korean standard become a vocabulary
   attribute in v1? The tag audit's `out_of_vocabulary_condition` column will show how often it
   appears.
3. **A missing campus:** should it be a branch attribute when the two campuses' rules differ, or is
   the default "ask the campus" when it is unstated?
