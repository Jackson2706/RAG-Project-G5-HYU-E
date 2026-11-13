# Slides outline (about 15 minutes + 8-minute demo)

Every number on a slide comes from `Report/results/test-final/` (tables in `Report/tables/test-final_*.md`).
The demo (`demo_script.md`) shows behaviour on dev cases only and is never used for a claim.

1. **Title.** HYU Compass: applicability-aware evidence sufficiency for new-student questions.
2. **Problem.** Relevant is not the same as eligible: the ERICA dormitory page for a Seoul student's question.
   The answer depends on campus, degree level, visa, TOPIK, academic status and term.
3. **System.** Modular RAG (one block per stage, presets, execution trace); the UI is runnable for every
   evaluated method; compare mode.
4. **Data.** Snapshot `hyu-20261110-97dc1269`: 362 English pages (306 Seoul, 56 ERICA), 1,867 chunks,
   applicability tags (rules first, LLM fallback).
5. **AAES.** Four steps: profile → applicability labels with a soft penalty (λ = 4, μ = 2) → branches by
   information gain → policy (ABSTAIN, CONFIRM, ANSWER, CONDITIONAL ≤ 3 branches, CLARIFY).
6. **Baselines and ablations.** B0, R5, R9-scope, R15, R16; brackets G0, G1; ablations A1-A4, A6.
7. **Labels.** 180 agent-written questions; LLM-annotated, adjudicated and verified (no human verification, A33);
   47 dev / 121 test / 12 excluded. Claims are relative comparisons.
8. **Protocol.** Defaults fixed before any run, dev for bug fixes only, config-freeze tag, one test run
   (resumed once after the Mac slept; logged in TEST_RUNS.md).
9. **Main result** (Figure `test-final_actions.png`). Acceptable action: B0 0.736, R15 0.711, G1 0.818, A0 0.248.
10. **Pre-registered comparisons.** AER vs R15: only 2 comparable cases, no difference (p = 1.0).
    Macro-F1 vs A4: −0.066 [−0.128, +0.000], Holm p = 0.393. Correctness: not computed.
11. **Why AAES fails here** (Figure `test-final_a0_confusion.png`). A2 (oracle profile) ≈ A0, so step 1 is
    not the cause; 35 of 52 clarifications ask for the campus; 27 of 46 abstain cases get a question.
12. **Slices** (Figure `test-final_slices.png`). A0 0.167-0.333 per slice vs B0 0.704-0.917.
13. **What we would change.** Ask only when branches give different answers; test sufficiency before
    branching. Not tried, because of the freeze.
14. **Limitations.** LLM labels, unaudited tags (G2b failed on three attributes), small slices, one generator,
    memory methods and ConditionalQA not run.
15. **Course mapping.** Relevance vs eligibility, candidate retrieval vs evidence selection, prefiltering vs
    postfiltering, sufficiency and abstention (Lesson 5), evaluation protocol (Lesson 6).
16. **Demo** (switch to the app; `demo_script.md`).
