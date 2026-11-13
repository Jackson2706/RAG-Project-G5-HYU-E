# HYU Compass: applicability-aware evidence sufficiency for new-student questions

Draft. Every number in this file comes from a file under `Report/results/` or `Sources/data/`; the source is
named next to it. Results sections are filled after the single test run (G6).

## 1. Problem

New international students at Hanyang University ask questions whose correct answer depends on who is
asking: the campus (Seoul or ERICA), the degree level, the visa, the TOPIK level, the academic status, and
the term. A standard RAG pipeline ranks passages by relevance. A passage can be relevant and still not apply
to the student: the ERICA dormitory procedure is relevant to a Seoul student's dormitory question, but it is
the wrong answer for that student. We call this the gap between relevance and eligibility.

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
   (from an earlier turn), stale, a scope default (not an applicant unless said), or missing. Nothing is guessed.
2. **Applicability labels and a soft penalty.** Each candidate chunk is labelled conflicting, unknown,
   unconditioned, compatible or open against the known profile. The reranker subtracts λ from the logit of a
   conflicting chunk and μ from a superseded version. Nothing is removed: candidate retrieval stays the same,
   and evidence selection changes.
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

(After G6. Source: `Report/results/test-final/`.)

## 7. Discussion

(After G6.)

## 8. Limitations

See `Report/notes/limitations.md`; the final list is copied here after G6.

## 9. Mapping to the course (Lessons 3-6)

(After G6.)
