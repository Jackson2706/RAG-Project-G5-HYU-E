# Slides outline (about 15 minutes + 8-minute demo)

Every number comes from `Report/results/` (test-1: `test-final/summary.md`, `summary_v2.md`, `posthoc.md`; dev:
`dev-03/`, `dev-04/ag_gate.json`). Case cards with the full replies are in `case_examples.md`. The demo
(`demo_script.md`) uses dev cases only and is never used for a claim. Labels are LLM-annotated (A33).

1. **Problem and AAES.** Relevant is not the same as eligible: the ERICA dormitory page for a Seoul student's
   question. The answer depends on campus, degree level, visa, TOPIK, academic status and term. AAES: profile →
   applicability labels with a soft penalty (λ = 4, μ = 2) → branches by information gain → policy (answer,
   conditional answer, clarify, abstain). Modular RAG with an execution trace; every method runs in the UI.
2. **Data and labels.** Snapshot `hyu-20261110-97dc1269`: 362 English pages, 1,867 chunks, applicability tags.
   180 agent-written questions, LLM-annotated, adjudicated and verified; 47 dev, 121 test-1, 12 excluded. Only 15
   test-1 cases (12%) need branching.
3. **Evaluator v1 → v2 (Lesson 6, slide 43).** v1 could not score a baseline as conditional or as a question. v2
   reads the reply text, was frozen on dev, κ = 0.899 against a blind annotator, and re-scored the saved test
   replies; no system re-run. B0 acceptable 0.736 → 0.661; R16 branch hits 0 → 2 of 15.
4. **Test-1 results (pre-registered, one run).** Acceptable action, v2: B0 0.661, R15 0.661, R16 0.628, G1 0.719,
   A0 0.256. AER vs R15: 2 comparable cases. Macro-F1 vs A4: −0.066, Holm 0.463, not significant. G0 closed book
   0.669: the action metric mostly measures answer vs referral.
5. **Where AAES helps.** On the 15 cases where the answer depends on the student: A0 right and B0 wrong 10, the
   reverse 0. Cards: T14-088 (part-time hours: B0 gives the Seoul figures to everyone), T14-051 (insurance sign-up:
   B0 gives ERICA's procedure to everyone), T14-155 (B0 calls a 2021 dorm notice current). Branch recall A0 10/15
   vs R16 2/15 (exact McNemar p = 0.0215, post hoc). But A3 (always ask) hits the same 10 plus one: the recall
   comes from being willing to ask.
6. **Where it hurts.** On the 46 cases the sources do not answer: A0 right and B0 wrong 1, the reverse 30. A0
   branches on 81 of 121 cases (precision 0.123); 35 of its 52 questions ask for the campus. Counter-example card
   T14-042 (one winter school, A0 asks "Seoul or ERICA?").
7. **Root cause in the code** (`app/rag/aaes.py`). Branches are which chunk IDs apply, not answer values (the
   labels count distinct answer values); the campus is always a candidate (1,775 of 1,867 chunks carry a site
   campus); `different_procedures` turns two-branch cases into questions; asking comes before any real sufficiency
   check. The design reached the spec only as a one-line summary, and no gate compared spec and labels.
8. **The guard and its result (dev only).** A0b (spec fixes, dev-03): acceptable 0.596 vs A0 0.362, no unnecessary
   questions, but branch recall 0/7. AG (R16 + a five-check guard, dev-04): fired once in 47 cases, wrongly;
   override precision 0.0, acceptable 0.617 vs R16 0.702: NO-GO. The fresh test-2 (75 cases, κ 0.773 / 0.708) was
   built and frozen but not used.
9. **Lessons and limitations.** Separate "when to ask" from "willing to ask" (compare with always-ask); check the
   spec against the labels before the test run; version the evaluator. Limitations: LLM labels, unaudited tags, 15
   branching cases, one 4B generator that is not reproducible word for word, an evaluator history bug found on
   dev, memory methods and ConditionalQA not run.
10. **Demo** (switch to the app; index r5 first; `demo_script.md`).
