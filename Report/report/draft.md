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
the prompted conditional baseline R16 and 0 for the other baselines. This counts reply types, not content: of
five A0 wins checked by hand, two had wrong or incomplete conditions and one the right action for the wrong reason.
Its own ablation A3, which asks whenever a
student detail is missing, finds the same 10 cases plus one more with the same precision, so on this test set
choosing when to ask from the evidence added nothing to branch recall. The recall comes from being willing to
ask. AAES also branches on 81 of 121 cases, so
its precision is 0.123, and its acceptable-action rate is 0.256 against 0.661 for basic dense RAG. We trace the
over-triggering to three rules in the code: branches are defined by which chunks apply, not by what they say;
the campus is always a candidate attribute; and the policy asks before it checks that any evidence answers the
question. A revised method built afterwards on dev only, a guard that keeps the best baseline's reply unless the
evidence clearly gives different answers, fired once in 47 dev cases, wrongly. It failed its pre-set dev check
(0.617 against 0.702 acceptable), so the fresh test set we built for it (75 cases) was not used. A post-hoc LLM judge
of answer quality (evaluator v3) finds that AAES covers fewer required facts than the baselines (0.119 against 0.300
for B0) but refers students to the right office much more often (0.724 against 0.340).

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

Comparison 2 needs a judge of answer correctness. None was validated before the test run, so it was reported as not
computed then. It is now computed post hoc on the saved replies with evaluator v3, an LLM judge (PLAYBOOK A36; section
6). v3 is validated against a second LLM judge, not against humans.

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
| 2. A0 vs R15, correctness | not computed at the run | v3, post hoc (unconditional slice, fact coverage): −0.185 [−0.312, −0.065], p = 0.0065; non-inferiority (−0.03) not met |
| 3. A0 vs A4, action macro-F1 | −0.066 [−0.128, +0.000], p = 0.131, Holm 0.393 | −0.066 [−0.132, +0.005], p = 0.154, Holm 0.463 |

Neither version separates A0 from R15 on AER, because only two cases are comparable. Neither shows a significant
macro-F1 difference between A0 and A4, and both point estimates favour A4.

**By slice** (v1, acceptable-action rate, `Report/tables/test-final_slices.md`, Figure 2): A0 reaches 0.333 on
conditional (27 cases), 0.292 on negative (24), 0.217 on unconditional (46), 0.167 on temporal (12) and 0.167 on
multi-session (12). B0 reaches 0.704, 0.708, 0.717, 0.750 and 0.917 on the same slices.

**Answer quality (evaluator v3, post hoc, LLM judge; `Report/results/quality_v3/summary.md`).** Fresh Opus 5.5
subagents judged every saved reply of B0, R15, R16, A0, G0 and G1, blind to preset names and in shuffled order, with
a prompt frozen before any test reply was judged (`Sources/evaluation/judge_v3_prompt.md`, sha256 prefix
3541b5db8960). Each answer is checked fact by fact against the label (correct, wrong or missing), for rules applied
to the wrong student group, and for whether each cited sentence is supported by its source. Questions are checked
for asking about a branch attribute, and referrals for naming the right office or next step. A second judge (Sonnet
5.5) re-judged 100 dev replies: κ = 0.859 on facts, 0.854 on wrong group, 0.791 on referral, 0.656 on "every cited
sentence supported", and 1.0 on the 15 questions and 10 conditional answers. The human check of 20 dev replies is
not filled in yet.

| Test-1 | Fact coverage | Wrong-fact rate | Wrong group | Citation support | Correct conditions (15 branching) | Useful question | Right referral |
|---|---|---|---|---|---|---|---|
| B0 | 0.300 | 0.117 | 0.265 | 0.573 | 0.000 | n/a | 0.340 |
| R15 | 0.269 | 0.133 | 0.194 | 0.561 | 0.000 | n/a | 0.333 |
| R16 | 0.258 | 0.133 | 0.224 | 0.520 | 0.000 | n/a | 0.267 |
| **A0** | 0.119 | 0.067 | 0.125 | 0.506 | 0.267 | 0.096 | 0.724 |
| G0 | 0.079 | 0.383 | 0.200 | n/a | 0.000 | n/a | 0.742 |
| G1 | 0.463 | 0.033 | 0.076 | 0.880 | 0.000 | n/a | 0.491 |

Fact coverage and the wrong-fact rate are over the 60 answer-expected cases; a reply that does not answer scores 0
coverage. Wrong group and citation support are over answered replies, the useful-question and referral rates over
that preset's questions and referrals. Paired bootstrap, post hoc and not Holm-corrected
(`quality_v3/comparisons.csv`):
- A0 covers fewer required facts than B0 (−0.181 [−0.281, −0.085], p = 0.0008) and R16 (−0.139 [−0.227, −0.057],
  p = 0.0028). It answers fewer of these cases (0.417 of them, against 0.633 for B0) and its answers cover fewer
  facts (0.287 against 0.474 among answered replies).
- A0 refers to the right office far more often: +0.385 [+0.174, +0.586] against B0 (p = 0.0006) and +0.457
  [+0.244, +0.657] against R16 (p = 0.0002).
- A0's answers apply a rule to the wrong group less often (0.125 against 0.265 for B0; −0.140 [−0.280, +0.001],
  p = 0.062) and contain a wrong fact less often (−0.050 [−0.138, +0.034]); neither difference is significant.
- On the 15 branching cases, A0's conditions or question are right in 0.267 of cases (4 of 15), against none for B0
  and R16 (+0.267 [+0.059, +0.500]; the permutation p of 0.121 does not confirm it).
- Only 0.096 of A0's 52 questions ask about an attribute the answer depends on. The rest are the unnecessary campus
  questions of section 7.
- Pre-registered comparison 2 (A0 vs R15, unconditional slice, 46 cases): fact coverage −0.185 [−0.312, −0.065], so
  A0 is not non-inferior within the 3-point margin.

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
- *A0 vs A3 and R16 on the 15 cases that need branching (v2, post hoc).* A0's 10 branch hits are a subset of
  A3's 11 (A3 adds T14-224), at almost the same precision (10/81 = 0.123 against 11/86 = 0.128). Against R16, 9
  cases are hit by A0 only and 1 by R16 only; an exact McNemar test gives p = 0.0215. This test is post hoc,
  exploratory and not Holm-corrected. This count compares reply types, not their content: of the five test-1 A0 wins checked by hand for the case cards, two had wrong or incomplete conditions (T14-121, T14-114) and one took the right action for the wrong reason (T14-155) (`Report/slides/case_examples.md`).
- *Why A0 asks (dev only).* The saved test records do not keep the AAES trace, and A34 forbids re-running a system
  on test, so we replayed A0's decision step on the 47 dev cases (`Sources/scripts/aaes_dev_diagnostics.py`,
  stopping before generation). All 47 actions matched the dev-02 run. Of the 21 dev questions, 16 had the reason
  `different_procedures` and 5 `many_branches`. Of the 25 dev cases where the campus branched, 20 had one campus
  with no applicable relevant chunk. A0 asked a question on 14 of those 20 and gave a conditional answer on 6
  (`Report/results/dev-02/a0_decisions_dev.jsonl`).

## 7. Discussion

AAES branches on the cases that need it and on many that do not. Under v2 it is the only method with branching behaviour where branching is expected: 10 of the 15 such test cases get a
conditional answer or a question, against 2 for R16 and none for the other retrieval baselines. This count compares reply types, not their content: of the five test-1 A0 wins checked by hand for the case cards, two had wrong or incomplete conditions (T14-121, T14-114) and one took the right action for the wrong reason (T14-155) (`Report/slides/case_examples.md`). Prompting a
model to give per-case answers, as R16 does, rarely produces them. Against its own ablation, however, AAES
gains nothing: A3, which asks whenever a student detail is missing, hits the same 10 cases and one more, at the
same precision. The branching recall comes from being willing to ask, not from choosing when to ask from the
evidence, so our research question (evidence-conditioned clarification beats always asking) is not supported on
this test set. A0, however, branches on 81 of the 121 cases, and most
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
run. The step-3 design (compare answer values; a branch without evidence is not a different answer) reached
`aaes_spec.md` only as a one-line summary, and no gate compared the spec with the label guideline. We list this
as a process limitation.

A next version would follow the design. It would branch only on distinct non-empty answer values, keep the campus
as a candidate only when there are campus-scoped chunks for both campuses, and run one yes/no sufficiency check
before any question. We implemented this as preset A0b and ran it on dev only, so the result is exploratory
and confirming it needs a fresh test set (`Report/results/dev-03/summary_v2.md`, evaluator v2, 47 dev cases). A0b
reaches 0.596 acceptable action against 0.362 for A0, 0.638 for B0 and 0.681 for R16, and it asks no unnecessary
question (0.000 against 0.425 for A0). It also finds none of the 7 dev cases that need branching, where A0 found 5
(`Report/results/dev-03/posthoc.md`). Under v2, A0b abstains on 4 of those 7 cases and answers 3. T14-044 is
the difference from its own actions: A0b decided ANSWER and the reply gives the contact route to the
question "How can I reach the international office?", so v1 counts it as an answer, while the v2 model labelled
it an abstention, apparently because the reply names the office. We count this as a v2 error. The saved records
keep the action and the reply but not the step details, so we can only partly say why A0b acted as it did. T14-209's abstention is the
"do not apply" template, which comes from the first ABSTAIN rule that A0 shares, not from the new yes/no check.
T14-032 and T14-120 get the "could not find" reply, which both new paths produce (the yes/no check said no, or
every extraction returned NONE); on A0's dev replay these cases had 7 and 5 branch rows, more than
`max_branches` = 3, which points to the yes/no check, but the record does not confirm it. Of the 4 answers,
T14-130 already had no branch in A0. T14-044 branched in A0 only on the campus, with no applicable chunk on
one side, so A0b answers through the campus rule or the empty branch, not through a merge. T14-017 and T14-132
branched in A0 on more than one attribute and answer in A0b through the campus rule, an empty branch or merged
answer values; the record does not say which. The merge is a real
risk in the code: `answer_key` and `distinct_answers` treat "up to 20 hours per week" and "up to 10 hours per
week" as the same answer (word-set Jaccard 3/5 = 0.6 ≥ 0.5), so branches that differ only in a number merge. We
did not fix or re-run A0b. The three changes remove the over-triggering and, on these cases, the branching with
it. A0b never ran on test (the runner plans it for dev only).

## 8. Revised method: dev result

**History.** After the test-1 run, and using dev only, we built two revisions. A0b (section 7, exploratory) fixed
the three code-level causes. A second revision, AG ("AAES guard", PLAYBOOK A35), takes the best dev baseline as its
base and changes its reply only when the evidence clearly gives different answers for different students. The plan
was to evaluate AG once on a fresh held-out set (test-2) if it passed a dev check fixed in advance.

**AG.** The base is R16. Under evaluator v2 on dev-02, R15 and R16 tie at 0.681 acceptable, and R16 has the higher
macro-F1 (0.374 against 0.356). AG returns R16's reply unchanged unless five checks all hold:
1. an unstated vocabulary attribute splits the selected evidence into at least two non-empty branches;
2. campus counts only when both campuses have campus-scoped evidence;
3. each branch is confirmed separately by one yes/no call;
4. the kept branches have different extracted answers, with numbers, amounts, dates, levels and yes/no compared
   exactly;
5. one call quotes the differing text of two branches, and both quotes must be found in their evidence.

When the guard fires, AG gives a conditional answer (at most 2 branches) or asks one question. Every check is
written to the trace. No threshold was tuned (`Sources/backend/app/rag/blocks/evidence/evidence_sufficiency/aaes_guard.py`).

**Dev check** (`Report/results/dev-04/ag_gate.json`, evaluator v2, 47 dev cases; the gate was fixed before the run:
GO only if AG is at least as good as R16 and at least 40% of its overrides are acceptable). The guard fired on 1 of
47 cases, T14-015 ("Can international researchers get counseling in English?"), and that override was wrong: it split
the answer by campus and degree level where the label expects one answer. Override precision was 0.0. AG's
acceptable-action rate was 0.617 against 0.702 for R16 (A0: 0.362); neither AG nor R16 asked an unnecessary question.
The result is **NO-GO**, so AG was not run on test-2 and is reported here as a dev result only.

Of AG's 4 breaks against R16, only T14-015 comes from the guard. T14-208 and T14-214 come from a bug in our
evaluator: it prepends a session's earlier turns to the question only for presets without profile understanding,
so AG's generator answered multi-session cases without the history R16 sees. T14-152 is run-to-run variation:
between dev-03 and dev-04, R16's own replies differ in wording on 25 of the 47 dev cases, with one acceptability
change. Neither changes the decision, because the precision condition fails on the single fire. We logged the bug
and did not re-run.

**Test-2.** The fresh set was built in parallel and frozen before any system ran on it (`Sources/data/HYU/labels/test2/NOTES.md`):
- 121 questions drafted blind from document titles, personas and the guidelines; 4 near-duplicates of earlier
  drafts dropped; 80 selected in test-1's slice and campus proportions;
- two blind annotators (Opus 5.5 and Sonnet 5.5), with agreement before adjudication of κ = 0.773 on
  answerability and κ = 0.708 on expected behaviour;
- adjudication by a third model where the first adjudicator shared a model with annotator A, then verification
  of every flagged case;
- 75 cases kept (`FROZEN_test2.sha256`).

After NO-GO it stays unused, available for a future method.

**What this shows.** The guard is conservative enough to leave R16's replies alone, but on dev it almost never
finds a case worth overriding, and its one override was wrong. A selective version of AAES that keeps the base
system's behaviour on ordinary questions removes the over-triggering, as A0b did, but we have no evidence yet that it
keeps the branching benefit seen on test-1.

## 9. Limitations

- Every question was written by an agent, and every label was annotated, adjudicated and verified by LLMs;
  nothing was checked by a human (A28, A33). Our numbers therefore compare methods on the same labels and are
  not absolute accuracy figures. Batches 04-06, the adjudication and the verification were all done by Claude
  models, so the annotators are independent contexts more than independent vendors.
- Agreement before adjudication was moderate: κ on answerability was 0.56 (Codex vs Opus) and 0.43 (Sonnet vs
  Opus), and 0.55 and 0.71 on the collapsed classes (`Report/results/labels/`).
- Evaluator v1 could not score a baseline as a conditional answer or a question; we found this after the test run.
  Evaluator v2 was written and frozen on dev before it touched test outputs, but it was designed after we had seen
  the v1 test results. Its validation compares it with one LLM annotator on 100 dev replies, not with humans, and
  the classifier is a 4B model. Agreement was κ = 0.899, so some replies are mislabelled. One example is dev case T14-044 in
  dev-03: A0b answered "How can I reach the international office?" with the contact route (a form or e-mail),
  and the v2 model labelled the reply an abstention, apparently because it names the office.
- The saved test records do not keep the AAES trace, so the reasons behind A0's questions come from a replay on
  dev, not from test.
- Process: the automatic G5 gate checked completion, not conformance to the design, so the gap between the
  labels' definition of a branch (distinct answer values) and the code's (applicable chunk sets) reached the test
  run, although dev already showed A0 below B0. The step-3 design reached `aaes_spec.md` only as a one-line
  summary, and no gate compared the spec with the label guideline.
- Twelve cases were excluded after the split, mostly because the right label needed gold spans for a campus
  branch that the primary label lacked. At least one dev case (T14-203) counts a campus as stated although the
  text never names it; we did not inspect the test split for this.
- The applicability tags were not audited by a human. The last tag audit (G2b, r4) failed on degree level,
  student type and visa, and the r5 round was not re-audited, although AAES depends on these tags.
- The revised method AG was checked on dev only and stopped there (NO-GO). Its dev run exposed an evaluator bug:
  earlier turns are prepended to the question only for presets without profile understanding, so AG answered
  multi-session cases without the history its base sees. Generation is also not reproducible word for word:
  R16's replies differ in wording on 25 of 47 dev cases between two runs, although only one acceptability label
  changes.
- On test-1, the presets whose step 1 is profile understanding or self-query (A0, A1, A3, A4, A6, R9S, R15)
  generated their multi-session replies without the earlier turns in the question; step 1 still received them.
  Of the 12 multi-session cases, the affected generated replies are A0 9, A1 8, A3 2, A4 8, A6 9, R9S 12 and R15 12
  (`Report/results/test-final/history_bug.json`); template replies (questions, referrals) are not affected.
- The fresh test-2 set (75 cases) was annotated and adjudicated only by LLMs, like test-1, and it was frozen but
  never run.
- Comparison 2 (correctness) was computed post hoc with an LLM judge (evaluator v3), after the test run. The judge was
  validated against a second LLM judge (κ 0.66 to 1.0 per field), not against humans; the 20-reply human check is
  pending. The cited [E#] markers could be matched to their chunks only when the counts agree (388 of 436 test
  replies with citations); otherwise all cited chunks count as the source.
- The test split has 121 cases and only 15 of them need branching, so the branching results rest on few cases.
  The per-slice numbers also rest on far fewer cases (counts in the slice table). We used one generator
  (`qwen3.5:4b`) on one 16 GB machine.
- The memory methods (M1, M2, A7), the LLM-judge ablation A5 and the external ConditionalQA benchmark were not
  run (PLAYBOOK A29).

## 10. Mapping to the course (Lessons 3–6)

Slide numbers refer to the lesson PDFs. "Status" says whether the idea is implemented and measured
(done), implemented but not measured or only measured on BEIR (partial), or deliberately left out (not done).

### Lesson 3: Ingestion, chunking and vector indexing

| Slide(s) | Course idea | Where it is in HYU Compass | Status |
|---|---|---|---|
| 8–9, 40 | Ingestion contract; the corpus is the source of truth; start from a manifest, not a directory glob | The crawler writes `Sources/data/HYU/manifest.jsonl` (one row per fetched URL) and a frozen snapshot `hyu-20261110-97dc1269`; the snapshot ID contains the first 8 hex digits of the manifest's sha256 | done |
| 10, 41 | Content hashes reveal changed sources; stable document IDs | `source_sha256` of the raw bytes per document; `doc_id = UUIDv5(canonical URL)` (`crawler/extract.py`) | done |
| 11–12, 51 | Parsers preserve provenance; normalization is minimal and versioned | Block-level English filter with `lang_coverage` per document; snapshot spans; VERIFY check `span_text_matches` re-reads the snapshot for every chunk | done |
| 14–17 | Chunking creates retrieval units; `s_tok`, `o_tok`; structure-aware boundaries | Section-aware chunks of 320/48 bge tokens; table rows repeat their header; English-only headers (VERIFY `no_hangul_headers`) | done |
| 18, 27, 50 | Stable chunk IDs; IDs bind content, policy and source span; anti-pattern: IDs that depend on loop order | `chunk_id = UUIDv5(doc_id, chunk index, sha256(text))` (`schemas.py`). The chunking policy is recorded in the index manifest rather than inside the ID | done (policy in manifest, not in ID) |
| 19, 30 | Metadata makes a vector inspectable; a point couples ID, vector and payload | Applicability tags in MongoDB, compact `app_*` filter fields in the Qdrant payload | done |
| 20, 44 | Embedding and index settings form one contract | `BAAI/bge-small-en-v1.5`, 384-d, cosine; VERIFY checks the dimension; the BGE query instruction is set in `config.py`. The model revision and library versions are not written into the index report | partial |
| 21–23, 36–37 | Exact search vs HNSW; HNSW trades exactness for speed | BEIR O7 vs O8 on identical vectors: ANN recall@10 = 1.0, about 6 ms either way, because the collections are small. HYU runs use exact search | partial (BEIR only) |
| 24, 28 | What must trigger re-embedding; incremental rebuild as a decision tree | `DATA.md` §5: r2 and r4/r5 changed tags only and needed 0 new LLM calls. Tags are not part of the embedded text (section heading + chunk text, `ingest_snapshot.embedded_text`), so a tag change does not require new vectors; each revision was still a full rebuild that reused the LLM tag cache | partial (full rebuilds, no incremental path) |
| 25, 31–32 | A checksum at every handoff; build → verify → publish; verification of counts, dimensions, IDs, provenance | `ingest_snapshot.py`: BUILD → VERIFY (15 checks) → PUBLISH; five index revisions r1–r5 kept for rollback; reports in `Report/results/index_reports/` | done |
| 34–35 | DPR; dense gains coexist with a lexical counterexample | BM25 (R1) vs dense (B0) on BEIR, Protocol B nDCG@10: SciFact 0.651 vs 0.716, NFCorpus 0.300 vs 0.346, ArguAna 0.452 vs 0.598 (`Report/results/2026-11-01_main`). Not run on HYU | done (BEIR) |
| 38–39 | Dense X: granularity is an experiment | BEIR chunk-size ablations O0–O5; no proposition-level index | partial |

### Lesson 4: The RAG mechanism, generation and grounding

| Slide(s) | Course idea | Where it is in HYU Compass | Status |
|---|---|---|---|
| 4–5 | Parametric vs external memory; RAG vs fine-tuning vs long context | G0 closed-book is the parametric-memory-only bracket; no fine-tuning; G1 gives gold evidence only | done |
| 6–7, 28 | Offline indexing vs question-time pipeline | The registry separates offline blocks (loading → indexing) from online blocks (query understanding → generation); one runner for app and evaluator | done |
| 10–11 | Passage size and overlap; provenance and source traceability | See Lesson 3 rows; every answer carries `[E#]` markers resolved to source URLs and spans | done |
| 15 | Lexical, dense and hybrid retrieval | BEIR: R1 BM25, B0 dense, R2 hybrid RRF, R5 hybrid + cross-encoder. HYU: B0 and R5 | done |
| 16 | Query formulation and rewriting | R6 rewrite (with validation and fallback to the original question), R7 multi-query, R8 HyDE (BEIR) | done (BEIR) |
| 17, 19 | Candidate set vs selected evidence; context construction | Candidate Top-K vs evidence Top-3; BEIR failure analysis: a relevant document retrieved but dropped by selection is the primary failure for 13% (SciFact), 14% (NFCorpus) and 35% (ArguAna) of B0 queries, Protocol B (`Report/results/2026-11-01_main/failure_analysis.csv`) | done |
| 18 | Retrieval and reranking | R3 coverage, R4 cross-encoder, R13 RankGPT (BEIR) | done (BEIR) |
| 20 | Context windows and token budgets | R11 token-budget selection (2,000 tokens); `num_ctx` 4,096 for every LLM call; the generator's value is recorded in each run's task config (`status.json`), the auxiliary calls use a fixed 4,096 in code | done |
| 22–25 | Claims; supported / contradicted / missing; citation and grounding | Source markers `[E1]…` resolved at runtime; claim-level support is offline evaluation by design (no online citation-verification block) | partial (claim support not scored: no validated judge) |
| 26 | Evidence sufficiency and abstention: "needed facts **and conditions** are available"; clarify an ambiguous request | The definition AAES operationalizes: conditions become applicability tags, and the policy chooses answer / conditional answer / clarify / abstain | done |
| 27 | Failure types and repair priorities | `evaluation/failure_analysis.py` labels the earliest failed stage per query | done |
| 30 | Retrieval quality and response quality are evaluated separately | Applicable-Recall@k and intrusion@k reported apart from action metrics | done |
| 31 | Freshness; conflicting sources need a policy for date, authority and scope; access rules | Version families and `superseded_by`; campus scope (national vs campus); the applicant scope default | done (only 3 superseded documents in the corpus, so the temporal rule never changed a decision: A6 takes A0's action on all 121 test cases) |
| 33–36 | RAG-Sequence / RAG-Token, Fusion-in-Decoder, FLARE | Not implemented: they need a trained reader or token-level retrieval during decoding, which local Ollama generation does not offer | not done (stated as out of scope) |
| 50 | Controlled comparison: one setting at a time | Each ablation (A1–A4, A6; A5 was not run) changes one part of A0; BEIR offline ablations change one factor | done |

### Lesson 5: Improving retrieval and deciding to proceed

| Slide(s) | Course idea | Where it is in HYU Compass | Status |
|---|---|---|---|
| 4 | Information need, relevance, evidence sufficiency | Applicability separates "relevant" from "applies to this student" | done |
| 7–12 | Rewriting, expansion, contextualization; semantic drift; validation and fallback | R6–R8 on BEIR; rewrite drift is a failure category | done (BEIR) |
| 13–16 | Metadata, typed predicates, Boolean logic; filtering by audience and policy year | Typed vocabulary v1 (9 attributes) with alternative condition sets for "TOPIK *or* English track" | done |
| 17–19 | Prefiltering vs postfiltering; candidate starvation; the response policy can clarify, abstain or retry | R9-scope and R15 prefilter; A1 hard filter vs A0 soft penalty; AAES actions follow slide 19's options | done |
| 21–24 | Pointwise, pairwise, listwise ranking; bi- vs cross-encoders | R4/R5 cross-encoder, R13 RankGPT listwise (BEIR) | done (no pairwise method) |
| 25–29 | Ranking vs the decision to proceed; scores vs decision signals; "enough evidence can support No" | AAES steps 2–4; the gold label counts a passage that proves a student is *not* eligible as evidence | done |
| 31–32 | Cost and latency; intervention provenance and rollback | `total_ms` and `llm_calls` per case; index revisions and configs versioned | done |
| 34–37 | Baselines, paired comparisons, ablations, regressions and improvement claims | Pre-registered comparisons with paired bootstrap and Holm correction; per-expected-behaviour and slice tables | done |
| 40–47 | Rewrite–Retrieve–Read, HyDE, RankGPT | R6, R8, R13 | done (BEIR) |

### Lesson 6: Evaluation, test sets and failure analysis

| Slide(s) | Course idea | Where it is in HYU Compass | Status |
|---|---|---|---|
| 5 | Separate targets: retrieval, answer, attribution, gate | Separate tables for retrieval, actions (gate) and AER; answer facts and citation support scored post hoc by evaluator v3 (LLM judge) | done (post hoc) |
| 6–7 | An inspectable record; case, system and evaluator versions | Run manifests store the label-file sha256 (case version), the git commit, configs and package versions (system version); the evaluator is versioned by its commit, and evaluator v2 records its classifier prompt hash (`summary_v2.md`) | done |
| 8–11 | What belongs in a case; coverage vs representativeness | Five slices sampled on purpose (conditional, temporal, negative, multi-session, unconditional), so averages are diagnostic, not representative | done |
| 12 | Relevance labels need a unit and a rubric | `GUIDELINES.md` v1.3: span-level gold, inapplicable and outdated evidence, expected behaviour | done |
| 14–19 | Recall, precision, reciprocal rank, nDCG | BEIR suite; Applicable-Recall@k on HYU | done |
| 20–22 | Answer quality; citation metrics need a counting unit | Evaluator v3: units are required facts and cited sentences; LLM judge validated against a second LLM judge, not humans | partial (post hoc, LLM judge) |
| 23–25 | A diagnostic tree locates the earliest defect | Failure categories by earliest stage; the A0 trace analysis in §6–7 | done |
| 26, 28, 30 | Dev vs test; threshold selection on dev; repeated test inspection changes what the test means | One test run (`TEST_RUNS.md`); no tuning of any method; post-hoc fixes evaluated on dev only | done |
| 27 | A gate confusion matrix evaluates a decision | Collapsed 2×2 (proceed vs withhold) plus the 4×4 action matrix | done |
| 31 | An overall improvement can hide a slice regression | Slice tables and per-expected-behaviour tables | done |
| 33 | Small samples limit conclusions | Bootstrap intervals; κ with intervals; the AER comparison had only 2 shared cases | done |
| 34–36 | Deterministic, model-based and human evaluators; a human audit can expose a judge error | Labels were LLM-annotated and LLM-adjudicated with no human audit: stated as the main limitation | not done (limitation) |
| 37–41 | RAGAS dimensions; ARES judge correction | RAGAS-style claim decomposition planned, not scored; ARES-style correction impossible without human labels | not done |
| 42 | RGB: behaviour under controlled contexts | The negative slice (no answer-bearing evidence) and conditional slice play RGB's role for abstention | partial |
| 43 | The evaluator rule can change a rejection score | Our own case: evaluator v1 inferred actions from the generation outcome only, so no baseline could ever be scored as giving a conditional answer or asking a question. Evaluator v2 classifies every method's final reply text the same way (§6, evaluator v1 vs v2). On the same saved test replies, B0's acceptable-action rate goes from 0.736 to 0.661 (`hyu_test_slices.csv` → `hyu_test_v2_slices.csv`), and R16's branch hits on the 15 cases that need branching from 0 to 2 (`posthoc_branch_detection.csv`), all in `Report/results/test-final/` | done (finding) |
