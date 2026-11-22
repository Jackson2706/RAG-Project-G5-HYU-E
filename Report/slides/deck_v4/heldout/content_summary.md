# Held-out content (deck v5 Phase 5), judged by Claude Opus 5.5 (v3 prompt)

Answered replies (answer / conditional_answer) of AAES+, AAES, B0 and R16 on test-3 + test-2: 475 items, shuffled and
split into 12 disjoint batches of ≤ 40, each judged by a separate Claude Opus 5.5 subagent that saw only the frozen v3
prompt (sha `3541b5db8960…`) and its batch. `key.jsonl` was opened only by `score-content` after all 12 were merged
(strict check: every item judged once, exact keys, facts lengths). Hashes of every part: `judge/content.json`.
**Labels and required facts are LLM-annotated; the judge is an LLM; no person checked either.** Claims are relative only.

## Scores (95% bootstrap CI over questions, 10,000 resamples, seed 0)

| Method | Slice | Answered replies | Facts covered | Replies with a wrong fact | Wrong-group replies | Cited sentences supported |
|---|---|---|---|---|---|---|
| AAES (A0) | all | 67 | 0.358 [0.278, 0.444] | 0.179 [0.090, 0.284] | 0.149 [0.075, 0.239] | 0.568 [0.442, 0.689] |
| AAES (A0) | student_dependent | 14 | 0.244 [0.095, 0.421] | 0.143 [0.000, 0.357] | 0.286 [0.071, 0.500] | 0.296 [0.121, 0.530] |
| AAES+ (RRRL) | all | 97 | 0.383 [0.316, 0.454] | 0.227 [0.144, 0.309] | 0.175 [0.103, 0.258] | 0.505 [0.400, 0.613] |
| AAES+ (RRRL) | student_dependent | 24 | 0.333 [0.212, 0.475] | 0.250 [0.083, 0.417] | 0.333 [0.167, 0.542] | 0.210 [0.092, 0.365] |
| standard dense (B0) | all | 145 | 0.407 [0.354, 0.463] | 0.324 [0.248, 0.400] | 0.241 [0.172, 0.317] | 0.544 [0.456, 0.628] |
| standard dense (B0) | student_dependent | 45 | 0.323 [0.242, 0.406] | 0.422 [0.289, 0.578] | 0.489 [0.333, 0.644] | 0.359 [0.223, 0.500] |
| prompted conditional (R16) | all | 166 | 0.453 [0.402, 0.508] | 0.295 [0.229, 0.367] | 0.223 [0.163, 0.289] | 0.539 [0.446, 0.627] |
| prompted conditional (R16) | student_dependent | 52 | 0.327 [0.258, 0.395] | 0.404 [0.269, 0.538] | 0.481 [0.346, 0.615] | 0.337 [0.202, 0.471] |

## Gold-evidence reference (G1, same judge procedure, 5 batches of ≤ 35; `judge/content_scores_gold.csv`)

| Method | Slice | Answered replies | Facts covered | Replies with a wrong fact | Wrong-group replies | Cited sentences supported |
|---|---|---|---|---|---|---|
| gold evidence (G1) | all | 171 | 0.609 [0.559, 0.659] | 0.135 [0.088, 0.187] | 0.181 [0.123, 0.240] | 0.837 [0.784, 0.884] |
| gold evidence (G1) | student_dependent | 57 | 0.541 [0.461, 0.621] | 0.228 [0.123, 0.333] | 0.509 [0.386, 0.632] | 0.775 [0.664, 0.869] |

With the right evidence the same small model covers 0.61 of the facts and cites correctly 84% of the time, but still
gives a wrong-group reply to half the student-dependent questions: retrieval limits the facts, the one-answer reply
limits the group.

## Reading

- Over its answered replies AAES+ covers about as many required facts as the others (0.383 vs AAES 0.358, B0 0.407, R16
  0.453; CIs overlap). It gives fewer wrong-group replies than B0 and R16 on student-dependent questions (0.333 vs 0.489
  and 0.481; CIs overlap) and fewer replies with a wrong fact overall (0.227 vs 0.324 and 0.295).
- These are rates over **each method's own answered replies** (97 for AAES+, 166 for R16), not paired over the same
  questions: AAES+ answers fewer questions, so it is scored on a different, partly easier set.
- Citation support is about half for every method (0.51–0.57): the small model often cites a source that does not say it.

## Judge consistency (reported by the subagents)

- Partly stated multi-part facts: batches 01, 02 and 09 mostly marked them *missing*; 04, 05, 06 and 10 mostly *correct*;
  11 decided per item with a note. Items were shuffled across methods, so this adds noise, not bias toward one method.
- A citation marker on its own line was counted for the sentence before it (05, 08, 09); markers written as (E1) were not
  counted (09, H0360); gold batch 01 did not count a marker standing alone (G0016). A reply that says information does not exist where the fact exists was judged *wrong* (05).
- Hard calls carry a `note` in `judge/judgments.jsonl`. Not re-judged: the prompt is frozen and no second judge was planned.

