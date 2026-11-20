# AAES+ freeze (deck v5, before the held-out run)

Frozen on top of commit `c989d8ea786ae1fce90f89dc89626b8f90dea727` (which already holds the held-out preset lists in evaluation/configs/hyu.yaml); the freeze commit adds only this file, selection.json, dev_ablation.csv and timing_v5.csv. The held-out run must start from the commit that contains this file.

**AAES+ = `AP_RRRL`**, chosen by the rule fixed before Stage B: AP_* with kept >= 0.8 * kept(A0_AAES = RRRR); highest acceptable_rate; ties: fewer llm_calls_mean, then preset name

Reference (A0_AAES = RRRR) kept 25 needed questions/splits on dev + dev-2; minimum for eligibility 20.0. Candidates: `aaes_plus/selection.json`, table `aaes_plus/dev_ablation.csv`.

## Held-out methods (this order, all seven per question)

1. `AP_RRRL`
2. `A0_AAES`
3. `AP_BBBB`
4. `B0_BASIC_DENSE_RAG`
5. `R15_SELF_QUERY`
6. `R16_PROMPTED_CONDITIONAL`
7. `G1_ORACLE_CONTEXT`

## Order rule

test-3 (140) first, then test-2 (75) only if at least 2.5 h remain before STOP_AT = 2026-11-21 12:00 KST; `--case-major` (every method on a question before the next question) and `--stop-at` (checked between questions); test-2 never started twice; test-1 never run. Qwen 3.5 4B, temperature 0, seed 42, thinking off, 4,096 context, index r5. Reply types: frozen evaluator v2.

## Pre-registered hypotheses (Holm-corrected over H1–H3; paired bootstrap 95% CI, 10,000 resamples, seed 0; McNemar)

- H1: `AP_RRRL` > `A0_AAES` on acceptable reply type, all held-out questions run (one-sided).
- H2: on student-dependent questions that need a question or split, `AP_RRRL` keeps them within 10 points of `A0_AAES` (non-inferiority: bootstrap 95% lower bound of the difference > −0.10).
- H3: `AP_RRRL` > `R16_PROMPTED_CONDITIONAL` on acceptable reply type on student-dependent questions (one-sided).
- Secondary (no correction): unneeded-question rate, wrong referrals, seconds per question.
- Only questions with a v2 reply type for every method are analysed (balanced); dropped ones are listed.

## Prompt hashes (SHA-256)

| Prompt | SHA-256 |
|---|---|
| PROFILE | `cfb20a23df521c0587f2d72b472e6711e99d2263d99b6218977b0be8513e920c` |
| APPLIES | `74ce6567690b04a8197b8ca3d17dfdb9b26bcf7a4573d5ff92612b3a2a1743d3` |
| DIFFERS | `21f4e50421777883f26223fe0fd5827fd8e2ee57cdb9cb095c93c9f7576dc099` |
| SAME | `12860b76d559250db6f78345df61df81c41ffbf7fecf889cf1edaf784f7f354a` |
| DECIDE | `a6b0cb927861a2ab29cfcd8d7d8de09c281a9bc2baa49a173adf22226489b3cd` |
| ASK | `af8aa193afa5052d73baecf25105c74ba33b6e744b6c097fd3e5d6e3faeda90f` |
| REFER | `e2022daabe5a726512f5fb7e136369669f4d0088ea24a5d5b1a945ad141fbbbb` |
| EXTRACT | `4e12bc8b40e307b4008aec6d7c9a20b824ae6dece84147dba2ac411fe749f8d9` |
| self_query.INSTRUCTION | `dc0113f54e5e515585ba9e689685eedef49d695ecc9f52b89f69e72c32540c98` |
| standard_context.SYSTEM_PROMPT | `062499d9a8cec7a050cec3a2cb480e1d0921f88d6b96036ffe05c4368cb200e7` |
| evaluator_v2 (reply_action.PROMPT) | `5151f273055b432072b376413f58b3039ad622cb11c0f21af02a61c4bc59a747` |
| judge_v3_prompt.md | `3541b5db89608e1bb3df8936cd9f187b5ab963071ede2ddba0b0290d1803c5ca` |
