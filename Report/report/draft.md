# HYU Compass: applicability-aware evidence sufficiency for new-student questions

Draft. Every number in this file comes from a file under `Report/results/` or `Sources/data/`; the source is
named next to it.

**Abstract.** New international students at Hanyang University ask questions whose answer depends on who is
asking (campus, degree level, visa, academic status), and a passage that is relevant to the question may not
apply to the student. We propose AAES (Applicability-Aware Evidence Sufficiency), which labels each retrieved
chunk against the student's profile and then answers, gives a conditional answer, asks one question, or abstains.
We compare it with five retrieval and prompting baselines, two brackets and five ablations on 121 frozen test
cases with LLM-annotated labels. The first evaluator (v1) could not score a baseline reply as conditional or as a
question, so we re-scored the saved replies with a reply-text classifier (v2). v2 agrees with a blind annotator at
κ = 0.899 on dev, and we did not re-run any system on test. Under v2, AAES is the only method that branches on
the cases that need it: it gives a conditional answer or a question on 10 of the 15 such cases, against 2 for
the prompted conditional baseline R16 and 0 for the other baselines. It also branches on 81 of 121 cases, so
its precision is 0.123, and its acceptable-action rate is 0.256 against 0.661 for basic dense RAG. We trace the
over-triggering to three rules in the code: branches are defined by which chunks apply, not by what they say;
the campus is always a candidate attribute; and the policy asks before it checks that any evidence answers the
question.

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

**Two evaluator versions (PLAYBOOK A34).** The action metrics need the action each method took.
- *Evaluator v1* (`evaluation/metrics/aaes.py`, `label_action`) takes the AAES action where there is one. For
  every other preset it maps the generation outcome to answer or abstain, so a baseline can never be scored as a
  conditional answer or a question, even when R16, which is prompted for both, writes one. We found this defect
  after the test run.
- *Evaluator v2* (`evaluation/reply_action.py`) reads the final reply that the student sees, for every preset
  alike. A reply is a conditional answer when it gives at least two cases conditioned on student attributes, a
  question when it asks and gives no final answer, an abstention when it gives no answer from the sources and
  refers the student elsewhere, and an answer otherwise. Fixed rules decide the AAES templates, the generator's
  refusal and replies with at least two "If you are ..." lines. `qwen3.5:4b` (temperature 0, seed 42, fixed prompt
  with hash `5151f273055b`) decides the rest. We wrote the rules and the prompt on dev outputs only and committed
  them before any test output was classified.

We validated v2 on a stratified sample of 100 dev replies. A fresh Opus 5.5 subagent labelled them from the reply
text alone, without preset names or v2 labels. Agreement was 0.93 and Cohen's κ = 0.899, above our 0.7 bar
(`Report/results/dev-02/v2_validation_summary.json`). We then re-scored the saved test replies without re-running
any system (`Report/results/test-final/summary_v2.md`, logged in `TEST_RUNS.md`). We report both versions. v2 is
the more accurate measure of what a student sees; v1 is the evaluator that was fixed before the test run.

## 6. Results

One test run on the 121 frozen test cases (`Report/results/test-final/`, `Report/results/TEST_RUNS.md`).
While the run was going, the Mac went to sleep on battery and three presets (G1, A0, A1) failed on database
timeouts. We resumed only those three, on the same run id and the same code. Table 1 is
`Report/tables/test-final_main.md`, Figure 1 is `Report/figures/test-final_actions.png`.

**Table 1. Test split, all slices (121 cases), evaluator v1.**

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

**Table 2. The same replies, evaluator v2** (`hyu_test_v2_slices.csv`; branch detection from
`posthoc_branch_detection.csv`, exploratory). Branch recall counts the 15 cases labelled conditional answer or
clarify on which the reply is a conditional answer or a question; precision divides by all such replies.

| Method | Answered | Action acc. | Acceptable | Macro-F1 | Unnecessary clarify | AER | Branch recall | Branch precision |
|---|---|---|---|---|---|---|---|---|
| B0 basic dense | 0.562 | 0.545 | 0.661 | 0.292 | 0.000 | 0.000 (0/9) | 0/15 | 0/1 |
| R5 hybrid + CE | 0.570 | 0.529 | 0.653 | 0.281 | 0.000 | 0.000 (0/6) | 0/15 | n/a |
| R9-scope prefilter | 0.587 | 0.521 | 0.653 | 0.277 | 0.000 | 0.333 (2/6) | 0/15 | n/a |
| R15 self-query | 0.554 | 0.545 | 0.661 | 0.291 | 0.000 | 0.286 (2/7) | 0/15 | n/a |
| R16 prompted conditional | 0.628 | 0.521 | 0.628 | 0.331 | 0.000 | 0.000 (0/5) | 2/15 | 2/10 |
| G0 closed book | 0.744 | 0.512 | 0.669 | 0.301 | 0.000 | 0.000 (0/8) | 1/15 | 1/2 |
| G1 gold evidence | 0.545 | 0.628 | 0.719 | 0.334 | 0.000 | 0.000 (0/5) | 0/15 | n/a |
| **A0 AAES** | 0.331 | 0.190 | 0.256 | 0.173 | 0.443 | 0.286 (2/7) | 10/15 | 10/81 |
| A1 hard filter | 0.339 | 0.190 | 0.256 | 0.175 | 0.462 | 0.286 (2/7) | 10/15 | 10/83 |
| A2 oracle profile | 0.322 | 0.207 | 0.273 | 0.190 | 0.415 | 0.333 (2/6) | 10/15 | 10/76 |
| A3 always clarify | 0.066 | 0.182 | 0.240 | 0.147 | 0.708 | 0.000 (0/1) | 11/15 | 11/86 |
| A4 question-only | 0.388 | 0.397 | 0.471 | 0.239 | 0.236 | 0.200 (1/5) | 1/15 | 1/26 |
| A6 no temporal rule | 0.331 | 0.198 | 0.264 | 0.180 | 0.443 | 0.286 (2/7) | 10/15 | 10/80 |

The AAES rows change little from v1 to v2, because AAES replies are templates or "If you are ..." cases. The
baselines lose answered cases: many replies that v1 counted as answers only explain what the evidence lacks, and
v2 counts them as abstentions. B0's acceptable rate falls from 0.736 to 0.661. AER has small denominators under
both versions, so the counts are in brackets.

**Pre-registered comparisons** under both evaluators (`hyu_test_comparisons_paired.csv`,
`hyu_test_v2_comparisons_paired.csv`; the best baseline, R15, was fixed on dev at G5):

| Comparison | v1 | v2 |
|---|---|---|
| 1. A0 vs R15, AER (conditional + temporal, both answered) | n = 2, diff 0.000, p = 1.0 | n = 2, diff 0.000, p = 1.0 |
| 2. A0 vs R15, correctness | not computed (no human-validated judge, A33) | not computed |
| 3. A0 vs A4, action macro-F1 | −0.066 [−0.128, +0.000], p = 0.131, Holm 0.393 | −0.066 [−0.132, +0.005], p = 0.154, Holm 0.463 |

Neither version separates A0 from R15 on AER, because only two cases are comparable. Neither shows a significant
macro-F1 difference between A0 and A4, and both point estimates favour A4.

**By slice** (v1, acceptable-action rate, `Report/tables/test-final_slices.md`, Figure 2): A0 reaches 0.333 on
conditional (27 cases), 0.292 on negative (24), 0.217 on unconditional (46), 0.167 on temporal (12) and 0.167 on
multi-session (12). B0 reaches 0.704, 0.708, 0.717, 0.750 and 0.917 on the same slices.

**Exploratory analyses** (not pre-registered; `Report/results/test-final/posthoc.md`).
- *Few cases need branching.* 15 of 121 test cases (12%) are labelled conditional answer (9) or clarify (6). The
  other 106 are labelled answer (60) or abstain (46). Our original plan set 15% as the share below which the
  branching question would not matter; the test split is close to that line.
- *Acceptable rate per expected behaviour (v2).* On the 9 conditional cases A0 is acceptable on 0.556 and on
  the 6 clarify cases on 0.833. Every baseline scores 0.000 on the clarify cases, and R16 scores 0.222 on the
  conditional ones. On the 60 answer cases A0 reaches 0.167 against 0.667 for B0, and on the 46 abstain cases
  0.239 against 0.870.
- *G0 as a base rate.* The closed-book bracket, which sees no evidence at all, reaches 0.669 acceptable under v2,
  above B0 (0.661). With 106 of 121 cases labelled answer or abstain, the acceptable-action rate mostly measures
  whether a method answers or refers on ordinary questions. It says little about branching.
- *Where A0's actions go (v2,* `hyu_test_v2_actions_confusion.csv`*).* A0 gives 52 questions and 29 conditional
  answers. Of the 60 cases labelled answer, it answers 8, gives a conditional answer to 17, asks on 20 and abstains
  on 15. Of the 46 cases labelled abstain, it abstains on 11 and asks on 27. Of its 52 questions, 35 ask for the
  campus, 7 for the degree level, 5 for the academic status, 3 for the student type and 2 for the TOPIK level
  (`posthoc_a0.csv`, from the CLARIFY templates in `raw/`).
- *Why A0 asks (dev only).* The saved test records do not keep the AAES trace, and A34 forbids re-running a system
  on test, so we replayed A0's decision step on the 47 dev cases (`Sources/scripts/aaes_dev_diagnostics.py`,
  stopping before generation). All 47 actions matched the dev-02 run. Of the 21 dev questions, 16 had the reason
  `different_procedures` and 5 `many_branches`. Of the 25 dev cases where the campus branched, 20 had one campus
  with no applicable relevant chunk. A0 asked a question on 14 of those 20 and gave a conditional answer on 6
  (`Report/results/dev-02/a0_decisions_dev.jsonl`).

## 7. Discussion

AAES branches on the cases that need it and on many that do not. Under v2 it is the only method with branching behaviour where branching is expected: 10 of the 15 such test cases get a
conditional answer or a question, against 2 for R16 and none for the other retrieval baselines. Prompting a
model to give per-case answers, as R16 does, rarely produces them. A0, however, branches on 81 of the 121 cases, and most
of the 106 ordinary cases need a plain answer or a referral. That is why its acceptable-action rate (0.256 under
v2) is far below the baselines (0.628 to 0.661). We checked the cause against the code in
`Sources/backend/app/rag/aaes.py`.

1. **Branches are defined by which chunks apply, not by what they say.** `information_gain` computes the entropy of
   the set of applicable chunk IDs over the values of an attribute. Two campus pages that state the same rule
   still give two different sets, so the campus has positive gain. The design (PLAYBOOK, step 3 "per-branch
   values") and the label guidelines (GUIDELINES: branch count = distinct answer values) define a branch by the
   answer value. `aaes_spec.md` step 3, which we wrote from that design, and the code define it by the applicable
   chunk set, and never compare answer values.
2. **The campus is always a candidate.** `_condition_attributes` starts from `{"campus"}`, and 1,775 of the
   1,867 chunks carry the campus of their site by default; only 92 are tagged national
   (`Report/results/index_reports/r5_campus_tags.json`). When a student does not name a campus, which is the usual case, the campus
   becomes a branch whenever chunks from both sites are relevant. This explains why 35 of A0's 52 test questions
   ask for the campus.
3. **Two documents force a question.** When the chunks that differ between branches come from more than one
   document, the policy returns CLARIFY with the reason `different_procedures`, even when there are only two
   branches. Seoul and ERICA pages are always different documents, so a two-branch campus case becomes a question
   instead of a conditional answer. On dev, 16 of A0's 21 questions had this reason.
4. **The question comes before a real sufficiency check.** A chunk counts as relevant when its lexical query
   coverage is at least 0.30, and ABSTAIN is chosen only when no relevant chunk applies. The policy branches
   before anything checks that the evidence answers the question. When nothing answers, a campus question only
   postpones the referral: 27 of the 46 test cases labelled abstain got a question. On dev, 20 of the 25 campus
   branches had no applicable relevant chunk on one side.

A2 receives the labelled `stated_profile` instead of running step 1.
It therefore measures only extraction errors on what the student said; it cannot show what the unstated gold
profile would change. A2 is close to A0 (acceptable 0.273 against 0.256 under v2), so extraction errors on stated
facts are not the cause. A6 (no temporal rule) takes the same action as A0 on all 121 cases. This is not a bug:
the snapshot has only 3 superseded documents in 2 version families, so the rule rarely has anything to act on.
A4, which asks from the question wording alone, asks less and is closer to the baselines (0.471), but it finds 1
of the 15 branching cases.

The problem was visible before the test run. On dev, A0 already scored 0.362 acceptable against 0.574 for B0
under v1 (`Report/results/dev-02/summary.md`). Our automatic G5 gate (A33) checked that the dev run completed and
that the comparisons were present. It did not check that the implementation matched the design and the labels, so
the gap between "distinct answer values" and `information_gain` reached the test
run. We list this as a process limitation.

A next version would follow the design. It would branch only on distinct non-empty answer values, keep the campus
as a candidate only when there are campus-scoped chunks for both campuses, and run one yes/no sufficiency check
before any question. We implemented this as preset A0b and ran it on dev only, so the result is exploratory
and confirming it needs a fresh test set (`Report/results/dev-03/summary_v2.md`, evaluator v2, 47 dev cases). A0b
reaches 0.596 acceptable action against 0.362 for A0, 0.638 for B0 and 0.681 for R16, and it asks no unnecessary
question (0.000 against 0.425 for A0). It also finds none of the 7 dev cases that need branching, where A0 found 5
(`Report/results/dev-03/posthoc.md`). The three changes remove the over-triggering and, on these cases, the
branching with it. The lexical comparison of extracted answers and the 4B extractor are the likely weak points; we
did not tune them. A0b never ran on test (the runner plans it for dev only).

## 8. Limitations

- Every question was written by an agent, and every label was annotated, adjudicated and verified by LLMs;
  nothing was checked by a human (A28, A33). Our numbers therefore compare methods on the same labels and are
  not absolute accuracy figures. Batches 04-06, the adjudication and the verification were all done by Claude
  models, so the annotators are independent contexts more than independent vendors.
- Agreement before adjudication was moderate: κ on answerability was 0.56 (Codex vs Opus) and 0.43 (Sonnet vs
  Opus), and 0.55 and 0.71 on the collapsed classes (`Report/results/labels/`).
- Evaluator v1 could not score a baseline as a conditional answer or a question; we found this after the test run.
  Evaluator v2 was written and frozen on dev before it touched test outputs, but it was designed after we had seen
  the v1 test results. Its validation compares it with one LLM annotator on 100 dev replies, not with humans, and
  the classifier is a 4B model.
- The saved test records do not keep the AAES trace, so the reasons behind A0's questions come from a replay on
  dev, not from test.
- Process: the automatic G5 gate checked completion, not conformance to the design, so the gap between the
  labels' definition of a branch (distinct answer values) and the code's (applicable chunk sets) reached the test
  run, although dev already showed A0 below B0.
- Twelve cases were excluded after the split, mostly because the right label needed gold spans for a campus
  branch that the primary label lacked. At least one dev case (T14-203) counts a campus as stated although the
  text never names it; we did not inspect the test split for this.
- The applicability tags were not audited by a human. The last tag audit (G2b, r4) failed on degree level,
  student type and visa, and the r5 round was not re-audited, although AAES depends on these tags.
- Comparison 2 (correctness) was not computed, because it needs an LLM judge validated against human labels.
- The test split has 121 cases and only 15 of them need branching, so the branching results rest on few cases.
  The per-slice numbers also rest on far fewer cases (counts in the slice table). We used one generator
  (`qwen3.5:4b`) on one 16 GB machine.
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

TODO (A34): replace this section with `section9_course_mapping.md` from the planning chat (the file did not reach
the session that rewrote sections 6-7) and fill its slide-43 cross-reference with the v1/v2 result in section 6.
