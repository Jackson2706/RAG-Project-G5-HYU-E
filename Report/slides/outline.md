# Slides outline (about 15 minutes + 8-minute demo)

Every number on a slide comes from `Report/results/test-final/` (v1: `summary.md`, v2: `summary_v2.md`, exploratory:
`posthoc.md`) or the dev files named in `Report/report/draft.md`. The demo (`demo_script.md`) shows behaviour on
dev cases only and is never used for a claim.

1. **Title.** HYU Compass: applicability-aware evidence sufficiency for new-student questions.
2. **Problem.** Relevant is not the same as eligible: the ERICA dormitory page for a Seoul student's question.
   The answer depends on campus, degree level, visa, TOPIK, academic status and term.
3. **System.** Modular RAG (one block per stage, presets, execution trace); every evaluated method runs in the UI;
   compare mode.
4. **Data.** Snapshot `hyu-20261110-97dc1269`: 362 English pages (306 Seoul, 56 ERICA), 1,867 chunks,
   applicability tags (rules first, LLM fallback).
5. **AAES.** Four steps: profile → applicability labels with a soft penalty (λ = 4, μ = 2) → branches by
   information gain → policy (ABSTAIN, CONFIRM, ANSWER, CONDITIONAL ≤ 3 branches, CLARIFY).
6. **Baselines and ablations.** B0, R5, R9-scope, R15, R16; brackets G0, G1; ablations A1-A4, A6.
7. **Labels.** 180 agent-written questions; LLM-annotated, adjudicated and verified (no human verification, A33);
   47 dev / 121 test / 12 excluded. Only 15 test cases (12%) need branching. Claims are relative comparisons.
8. **Protocol.** Defaults fixed before any run, dev for bug fixes only, config freeze, one test run (resumed once
   after the Mac slept). Evaluator versioning (Lesson 6): v1 could not score a baseline as conditional or as a
   question; v2 reads the reply text, was frozen on dev, κ = 0.899 against a blind annotator, then re-scored the
   saved test replies. No system re-run.
9. **Main result, both evaluators.** Acceptable action, v1 → v2: B0 0.736 → 0.661, R16 0.694 → 0.628,
   G1 0.818 → 0.719, A0 0.248 → 0.256. AAES stays far behind on the ordinary cases.
10. **What AAES gets right** (v2, exploratory). Branch recall on the 15 cases that need it: A0 10/15, R16 2/15,
    the other baselines 0/15. On the 6 clarify cases A0 is acceptable on 0.833; every baseline on 0.000.
11. **What it gets wrong.** A0 branches on 81 of 121 cases (precision 0.123). 52 questions, 35 of them about the
    campus; 27 of the 46 abstain cases get a question. G0 closed book reaches 0.669 under v2: the action metric
    mostly measures answer vs referral on ordinary questions.
12. **Why, in the code** (`app/rag/aaes.py`). Branches = which chunk IDs apply, not answer values (the labels count
    distinct answer values); the campus is always a candidate and 1,775 of 1,867 chunks carry a site campus;
    `different_procedures` turns two-branch cases into questions (16 of 21 on dev); asking comes before any real
    sufficiency check (coverage ≥ 0.30 only).
13. **Pre-registered comparisons, v1 and v2.** AER vs R15: 2 comparable cases, no difference under both.
    Macro-F1 vs A4: −0.066 under both (Holm 0.393 / 0.463), not significant. Correctness: not computed.
14. **Ablations read correctly.** A2 gets the stated profile, so it only tests extraction of stated facts
    (0.273 vs 0.256). A6 = A0 on every action: only 3 superseded documents. Dev already showed the gap
    (A0 0.362 vs B0 0.574); our automatic gate checked completion, not design conformance.
15. **What we would change, tried on dev only (A0b, exploratory).** Branch on distinct answer values; campus only
    when both campuses have scoped chunks; one yes/no check before any question. Dev, v2: acceptable 0.596 vs A0
    0.362 (B0 0.638, R16 0.681), unnecessary clarification 0.000, but branch recall 0/7 (A0 5/7). Needs a fresh
    test set.
16. **Limitations.** LLM labels, unaudited tags (G2b failed on three attributes), evaluator v2 designed after
    seeing v1 test results (frozen on dev), 15 branching cases, one generator.
17. **Course mapping.** Relevance vs eligibility, candidate retrieval vs evidence selection, prefiltering vs
    postfiltering, sufficiency and abstention (Lesson 5), evaluation protocol and evaluator versioning (Lesson 6).
18. **Demo** (switch to the app; `demo_script.md`; index r5 selected first).
