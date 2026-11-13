# HYU Compass: applicability-aware evidence sufficiency for new-student questions

Draft. Every number in this file comes from a file under `Report/results/` or `Sources/data/`; the source is
named next to it.

## 1. Problem

New international students at Hanyang University ask questions whose correct answer depends on who is
asking: the campus (Seoul or ERICA), the degree level, the visa, the TOPIK level, the academic status, and
the term. A standard RAG pipeline ranks passages by relevance. A passage can be relevant and still not apply
to the student: the ERICA dormitory procedure is relevant to a Seoul student's dormitory question, but it is
the wrong answer for that student. This is the gap between relevance and eligibility.

Our contribution, AAES (Applicability-Aware Evidence Sufficiency), treats evidence as sufficient only when it
answers the question and applies to the asking student. When it does not, the system gives a conditional
answer, asks one clarifying question, or abstains and refers the student to the right office.

## 2. Data

**Corpus.** Official English pages of the two international offices, crawled once and frozen as snapshot
`hyu-20261110-97dc1269` (`Sources/data/DATA.md`): 362 documents, 306 Seoul and 56 ERICA, with 10 aliases, 2
version families and 3 superseded documents. The crawl followed robots.txt, one request at a time at least
2.5 s apart. Staff directories were not crawled and every e-mail address is masked. The index has 1,867
section-aware chunks of 320 tokens with a 48-token overlap (`BAAI/bge-small-en-v1.5`).

**Applicability tags (offline AAES step).** Each chunk carries a condition: the campus, constraints on the
vocabulary attributes (degree level, year, student type, visa, TOPIK level, English track, academic status,
Korean-language standard, term), alternative condition sets, a scope (campus or national), and a condition
status (unconditioned, rule-tagged, or unknown). Tags come from rules first and an LLM fallback second
(`Sources/docs/aaes_spec.md`, index revision r5).

**Questions and labels.** 180 questions in five slices: unconditional, conditional, temporal, negative and
multi-session. All were agent-written; no question was written by a human (PLAYBOOK A28). Each case has a
stated and a gold profile, the answerability, the expected behaviour (answer, conditional answer, clarify,
abstain) with the acceptable alternatives, the branch attributes, required facts, and character spans for gold,
inapplicable and outdated evidence (`Sources/data/HYU/labels/GUIDELINES.md`, v1.3).

Labels were produced in autonomous mode (PLAYBOOK A33). Codex annotated batches 01-03 and Sonnet 5.5 batches
04-06. A fresh Opus 5.5 context adjudicated 47 disputed or flagged rows. Deterministic checks flagged 99 cases.
Fresh Opus 5.5 contexts then verified every test case and every flagged case. Twelve cases were excluded, so the
frozen split has 47 dev and 121 test cases (`Sources/data/HYU/labels/excluded.jsonl`, `Report/project/gates.md`).
Nothing was verified by a human: all comparisons below are relative comparisons between methods on an
LLM-annotated test set.

## 3. Method: AAES

AAES adds four online steps to a hybrid retrieval pipeline (BM25 + dense, reciprocal rank fusion,
cross-encoder reranking). Every step writes its typed input and output to the execution trace.

1. **Profile.** Rules read the question and the earlier user turns. Each attribute is stated, remembered
   (from an earlier turn), stale, a scope default (not an applicant unless said), or missing; no value is guessed.
2. **Applicability labels and a soft penalty.** Each candidate chunk is labelled conflicting, unknown,
   unconditioned, compatible or open against the known profile. The reranker subtracts λ from the logit of a
   conflicting chunk and μ from a superseded version. No chunk is removed, so candidate
   retrieval stays the same and only evidence selection changes.
3. **Branches and information gain.** For each unknown attribute, AAES checks whether its values change which
   relevant evidence applies. The information gain of an attribute is the entropy of those outcomes. An
   attribute with positive gain is a branch.
4. **Policy.** ABSTAIN when no relevant evidence applies, and refer the student to their own campus office.
   CONFIRM a stale value that matters. ANSWER when nothing branches. A CONDITIONAL answer when the branches are
   few (at most `max_branches` = 3) and share one procedure. Otherwise CLARIFY with one question on the attribute
   with the highest gain. CLARIFY, CONFIRM and ABSTAIN use fixed templates and no LLM call. An answer that rests
   on evidence of unknown condition status gets a caveat.

**Parameters.** λ = 4.0, μ = 2.0, `max_branches` = 3, relevance threshold 0.30 (query coverage, Lesson 5).
These are the defaults fixed on 2026-11-13. Nothing was tuned: dev runs were used only to find bugs
(`Report/results/configs/defaults-20261113.json`).

**Ablations.** A1 removes conflicting chunks instead of penalising them (prefiltering-style hard filter).
A2 gives AAES the labelled stated profile instead of step 1 (oracle profile). A3 always clarifies when any
attribute of a relevant chunk's condition is unknown. A4 decides to ask from the question wording alone,
without looking at how the evidence splits. A6 removes the temporal rule.

## 4. Baselines and brackets

| ID | Method |
|---|---|
| B0 | Basic dense RAG (the original app: Top-5 cosine, Top-3 evidence) |
| R5 | Hybrid retrieval + cross-encoder |
| R9-scope | Prefilter on the student's stated profile before retrieval |
| R15 | Self-query retriever: an LLM writes a metadata filter from the question |
| R16 | Prompted conditional answering: R5's retrieval, the prompt asks for conditions per case or one question |
| G0 | Closed book (lower bracket) |
| G1 | Gold evidence given to the generator (upper bracket) |

All generation uses `qwen3.5:4b` (temperature 0, seed 42, thinking off) through Ollama on one 16 GB Mac.

## 5. Evaluation setup

Metrics (`Sources/docs/aaes_spec.md`, "Metrics"):
- action accuracy, acceptable-action rate and action macro-F1 over answer / conditional / clarify / abstain;
- unnecessary-clarification rate;
- Applicable-Recall@k and Inapplicable-Intrusion@k (evidence selection);
- applicability error rate (AER): an answered case cites an inapplicable span;
- outdated-answer rate;
- unknown-caveat rate.

Pre-registered comparisons, Holm-corrected, with paired bootstrap 95% intervals and paired permutation tests:
1. A0 vs the best of {B0, R5, R15, R16} on AER (conditional + temporal slices);
2. A0 vs the same baseline on correctness (unconditional slice, non-inferiority margin 3 points);
3. A0 vs A4 on action macro-F1.

Comparison 2 needs an LLM judge validated against human labels. Without human labels (A33) it is reported as
not computed.

## 6. Results

One test run on the 121 frozen test cases (`Report/results/test-final/`, `Report/results/TEST_RUNS.md`).
While the run was going, the Mac went to sleep on battery and three presets (G1, A0, A1) failed on database
timeouts. We resumed only those three, on the same run id and the same code. Table 1 is
`Report/tables/test-final_main.md`, Figure 1 is `Report/figures/test-final_actions.png`.

**Table 1. Test split, all slices (121 cases).**

| Method | Answered | Action acc. | Acceptable | Macro-F1 | Unnecessary clarify | AppRecall@5 | AER |
|---|---|---|---|---|---|---|---|
| B0 basic dense | 0.835 | 0.587 | 0.736 | 0.288 | 0.000 | 0.469 | 0.000 (0/11) |
| R5 hybrid + CE | 0.818 | 0.521 | 0.669 | 0.249 | 0.000 | 0.428 | 0.091 (1/11) |
| R9-scope prefilter | 0.835 | 0.521 | 0.686 | 0.245 | 0.000 | 0.463 | 0.300 (3/10) |
| R15 self-query | 0.835 | 0.545 | 0.711 | 0.263 | 0.000 | 0.411 | 0.250 (3/12) |
| R16 prompted conditional | 0.860 | 0.545 | 0.694 | 0.255 | 0.000 | 0.428 | 0.167 (2/12) |
| G0 closed book | 1.000 | 0.496 | 0.661 | 0.166 | 0.000 | n/a | 0.000 (0/13) |
| G1 gold evidence | 0.727 | 0.669 | 0.818 | 0.350 | 0.000 | n/a | 0.000 (0/6) |
| **A0 AAES** | 0.347 | 0.174 | 0.248 | 0.160 | 0.443 | 0.459 | 0.286 (2/7) |
| A1 hard filter | 0.355 | 0.165 | 0.240 | 0.155 | 0.462 | 0.461 | 0.286 (2/7) |
| A2 oracle profile | 0.355 | 0.165 | 0.248 | 0.156 | 0.415 | 0.467 | 0.286 (2/7) |
| A3 always clarify | 0.083 | 0.182 | 0.248 | 0.148 | 0.708 | 0.459 | 0.000 (0/1) |
| A4 question-only | 0.521 | 0.388 | 0.496 | 0.226 | 0.236 | 0.459 | 0.125 (1/8) |
| A6 no temporal rule | 0.347 | 0.174 | 0.248 | 0.160 | 0.443 | 0.459 | 0.286 (2/7) |

AER is a share of answered cases whose labels mark an inapplicable span, so its denominators are small; the
counts are in brackets (from `hyu_test_per_case.csv`).

**Pre-registered comparisons** (`hyu_test_comparisons_paired.csv`; the best baseline, R15, was fixed on dev at G5):

1. A0 vs R15 on AER (conditional + temporal): only 2 cases with inapplicable spans were answered by both
   methods, with a difference of 0.000 (p = 1.0), so the test cannot separate them.
2. A0 vs R15 on correctness: not computed (no human-validated judge, A33).
3. A0 vs A4 on action macro-F1: −0.066, 95% CI [−0.128, +0.000], p = 0.131, Holm-corrected p = 0.393; the
   difference is not significant, and the point estimate favours A4.

**By slice** (acceptable-action rate, `Report/tables/test-final_slices.md`, Figure 2): A0 reaches 0.333 on
conditional (27 cases), 0.292 on negative (24), 0.217 on unconditional (46), 0.167 on temporal (12) and 0.167 on
multi-session (12). B0 reaches 0.704, 0.708, 0.717, 0.750 and 0.917 on the same slices.

**Where A0's actions go** (`hyu_test_actions_confusion.csv`, Figure 3). Of 60 cases labelled *answer*, A0
answered 7, gave a conditional answer to 19, asked a question on 20 and abstained on 14. Of 46 cases labelled
*abstain*, it abstained on 10 and asked a question on 27. Of its 52 clarifying questions, 35 asked for the
campus (from the A0 answers in `raw/`).

## 7. Discussion

On this test set AAES did not improve the system's actions. We asked whether separating relevance from
eligibility leads to better actions, and on our LLM-annotated labels it led to worse ones: A0 chose an
acceptable action in 24.8% of cases, against 73.6% for the plain dense baseline B0. The evidence we planned for
the method, a lower applicability error rate than the best baseline, could not be obtained, because A0 answered
so rarely that only two cases were comparable.

Profile extraction (step 1) is not the cause. A2, which receives the labelled profile instead of extracting it,
behaves almost exactly like A0 (acceptable 0.248; unnecessary clarification 0.415 against 0.443). The problem
lies in the branch test and the policy (steps 3 and 4). Most questions retrieve relevant pages from both
campuses while the campus is usually unstated, so the campus always splits the evidence and AAES asks for it;
35 of its 52 clarifying questions are about the campus. In the dev cases we inspected (for example T14-015,
counselling in English), the two campus pages give the same answer, or the label expects an abstention because
neither page answers. The branch test checks whether the applicable evidence changes with an attribute; it does
not check whether the answer changes, and we consider this the main design gap.

AAES also asks where it should abstain: 27 of the 46 cases that should end in a referral received a clarifying
question. AAES computes branches before it checks that any evidence answers the question, so when nothing
answers, a question about the campus only postpones the abstention.

Most ablations stay close to A0. A1 (hard filter instead of the penalty) is within one case of A0, and A6 (no
temporal rule) is identical, so the temporal rule never changed a decision on these cases. A3 (always clarify)
shows the cost of asking, with 70.8% unnecessary clarifications. A4, which decides to ask from the question
wording alone, asks less and does better than A0 (acceptable 0.496), although the macro-F1 difference is not
significant.

The baselines are close to each other. The four retrieval baselines are within 6.7 points of B0 in acceptable
action, and B0 is the best of them. Neither prefiltering on the stated profile (R9-scope) nor an LLM-written
filter (R15) reduced AER on the few comparable cases. The gold-evidence bracket G1 reaches 0.818, so better
evidence selection could still help, and the closed-book bracket G0 at 0.661 shows how much of the label set a
model can match without any retrieval.

Eligibility still matters for these questions: every retrieval baseline except B0 cited an inapplicable span
in at least one answered case. Deciding *when to ask* from how the evidence splits, however, needs a test on
the answers as well as on the evidence conditions. A next version would check that the branches lead to
different answers before asking, and would test sufficiency before branching. We did not try these changes,
because no parameter or rule was changed after the configuration freeze (G5) and dev runs were used only to
fix bugs.

## 8. Limitations

- Every question was written by an agent, and every label was annotated, adjudicated and verified by LLMs;
  nothing was checked by a human (A28, A33). Our numbers therefore compare methods on the same labels and are
  not absolute accuracy figures. Batches 04-06, the adjudication and the verification were all done by Claude
  models, so the annotators are independent contexts more than independent vendors.
- Agreement before adjudication was moderate: κ on answerability was 0.56 (Codex vs Opus) and 0.43 (Sonnet vs
  Opus), and 0.55 and 0.71 on the collapsed classes (`Report/results/labels/`).
- Twelve cases were excluded after the split, mostly because the right label needed gold spans for a campus
  branch that the primary label lacked. At least one dev case (T14-203) counts a campus as stated although the
  text never names it; we did not inspect the test split for this.
- The applicability tags were not audited by a human. The last tag audit (G2b, r4) failed on degree level,
  student type and visa, and the r5 round was not re-audited, although AAES depends on these tags.
- Comparison 2 (correctness) was not computed, because it needs an LLM judge validated against human labels.
- The test split has 121 cases, and the per-slice numbers rest on far fewer (counts in the slice table). We used
  one generator (`qwen3.5:4b`) on one 16 GB machine.
- The memory methods (M1, M2, A7), the LLM-judge ablation A5 and the external ConditionalQA benchmark were not
  run (PLAYBOOK A29).

## 9. Mapping to the course (Lessons 3-6)

| Course idea | Where it is in HYU Compass |
|---|---|
| Relevance vs eligibility | The core of AAES: a chunk can be relevant and still not apply to the student (applicability labels, step 2). |
| Candidate retrieval vs evidence selection | AAES leaves candidate retrieval unchanged and changes evidence selection only (soft penalty λ, μ). |
| Prefiltering vs postfiltering | R9-scope and R15 prefilter on profile tags before retrieval; A1 removes conflicting chunks after it; A0 penalises instead of removing. |
| Evidence sufficiency and abstention (Lesson 5) | The relevance threshold is Lesson 5's query-term coverage (0.30); AAES extends sufficiency with applicability and abstains with a referral. |
| Evaluation (Lesson 6) | Dev/test separation with a frozen test split and one test run; the gate convention "actual positive = sufficient, predicted positive = proceed"; grounding and citation-precision code checked on the Lesson 6 slide examples. |

TODO (team): Lessons 3 and 4 are not cited anywhere in the repository and the slides are not on this machine.
Map the modular pipeline (one block per stage, presets, execution trace) to the right lesson before submission.
