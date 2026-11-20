# Held-out results (deck v5 Phase 3)

One run from the frozen commit `4e6d007` (`aaes_plus_freeze.md`): test-3 (140) 19:58–00:03, test-2 (75) 00:03–01:26 KST,
every method on a question before the next. One AAES+ test-3 reply (N038) failed on an Ollama Metal GPU error and was
retried once as a recorded resume (`Report/results/TEST_RUNS.md`). Reply types: frozen evaluator v2. All 215 questions
have a reply type for all seven methods (0 dropped). **Labels are LLM-annotated, adjudicated and verified by one model;
no person checked them.** Script: `python scripts/deck_v5.py heldout --run heldout-test3,heldout-test2 --splits test3,test2 --ours AP_RRRL`.

## Reply types (test-3 + test-2, 215 questions; student-dependent 70)

| Method | Acceptable (all) | Acceptable (student-dependent) | Unneeded questions/splits (all) | Wrong referrals (all) |
|---|---|---|---|---|
| AAES+ (RRRL) | 0.395 | 0.671 | 0.414 | 0.153 |
| AAES (A0) | 0.312 | 0.657 | 0.516 | 0.144 |
| all-both (BBBB) | 0.563 | 0.314 | 0.098 | 0.144 |
| standard dense (B0) | 0.544 | 0.086 | 0.005 | 0.237 |
| self-query (R15) | 0.577 | 0.143 | 0.000 | 0.209 |
| prompted conditional (R16) | 0.609 | 0.200 | 0.019 | 0.135 |
| gold evidence (G1) | 0.674 | 0.086 | 0.000 | 0.070 |

Per split and slice: `reply_types.csv`.

## Pre-registered hypotheses (Holm over H1–H3; paired bootstrap 95% CI; McNemar)

| | Comparison | n | AAES+ | Baseline | Difference [95% CI] | Holm p | Decision |
|---|---|---|---|---|---|---|---|
| H1 | acceptable vs A0_AAES | 215 | 0.395 | 0.312 | +0.084 [+0.042, +0.126] | 0.0001 | superior |
| H2 | kept vs A0_AAES | 66 | 0.697 | 0.727 | -0.030 [-0.076, +0.000] | 0.5000 | non_inferior |
| H3 | acceptable vs R16_PROMPTED_CONDITIONAL | 70 | 0.671 | 0.200 | +0.471 [+0.329, +0.614] | 0.0000 | superior |

H2 is decided by the CI rule (lower bound > −0.10); its McNemar p is descriptive.

Secondary (no correction):
- vs A0_AAES, unneeded: -0.102 [-0.144, -0.065]
- vs A0_AAES, wrong_referral: +0.009 [+0.000, +0.023]
- vs A0_AAES, seconds: +10.045 [+9.044, +11.121] (medians 8.8 s vs 0.4 s)
- vs R16_PROMPTED_CONDITIONAL, unneeded: +0.395 [+0.330, +0.460]
- vs R16_PROMPTED_CONDITIONAL, wrong_referral: +0.019 [-0.042, +0.079]
- vs R16_PROMPTED_CONDITIONAL, seconds: -0.993 [-2.236, +0.235] (medians 8.8 s vs 10.2 s)

## Example traces

1. **AAES+ fixed an AAES error (test-2 T2-011, label: answer).** "Tell me about the International Winter School, what is it
   about?" AAES: "The answer depends on your campus. Which applies to you: Seoul or ERICA?" (unneeded). AAES+: "The Hanyang
   International Winter School (HIWS) is one of the programs directly responsible for by the Office of International Affairs
   (OIA). … [E2]" — the held-out twin of the dev winter-school failure (T14-042).
2. **AAES+ broke a correct reply (test-2 T2-017, label: answer per case or ask).** "Where is the Office of International
   Affairs and how can I reach them?" AAES asked the campus (acceptable). AAES+ answered for Seoul only: "… International
   Building (#108), 222 Wangsimri-ro, Seongdong-gu, Seoul … +82-2-2220-2453~2460 [E2]" — an ERICA student gets the wrong office.
3. **Student-dependent success (test-2 T2-009, label: answer per case or ask).** "How can I sign up for counseling services
   as an international student?" AAES+: "If you are at the Seoul campus, you should ask the OIA office … If you are at the
   ERICA campus, you can access psychological counseling services through the university's dedicated center … [E2]".
   Prompted conditional answering (R16): "To request counseling, please email us at the address below. [E3]" (one answer for
   everyone, and no address).

