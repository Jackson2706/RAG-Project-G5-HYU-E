# Follow-up fix, dev check (deck v6 Task 1) — post-hoc, dev only

**Fix:** after an AAES clarifying question, a detail-only reply ("I'm a Seoul campus student.") answers the earlier
question; the detail is a stated attribute (`Sources/backend/app/rag/followup.py`, flag `followup_resolution`: on in
the app, off in every frozen run). **Accepted for the demo:** the regression check is identical and reply-only facts
covered rose above 0.

**Regression** (47 dev single-turn questions, LLM cache on; `Report/results/deck6-regress-off`, `deck6-regress-on`):
A0 and AP_RRRL give the same reply type and the same reply text on all 94 replies with the flag off and on.

**Dev check:** Task 2 "reply only" again, same 39 personas and reply sentences, A0 and AP_RRRL with the fix; reply
types by evaluator v2; content judged blind by GPT-6 Sol with the frozen v3 prompt (3 batches of 26, merged by
`merge_judgments`; `judge/judgments.meta.json`). 104 of the 107 detail replies were resolved to the earlier question
(the other 3 were "I'm not sure." or a detail Step 1 cannot read, and ran as before).

| Reply only | Facts covered | Wrong fact | Wrong group | Turns per persona | Answer after one reply | Mean score (0–2) |
|---|---|---|---|---|---|---|
| A0, Phase 4 (before) | 0.000 | 0.000 | 0.080 | 2.79 | 10 of 39 | 0.154 |
| A0 with the fix | 0.205 | 0.136 | 0.269 | 2.64 | 13 of 39 | 0.333 |
| AAES+ (AP_RRRL) with the fix | 0.255 | 0.128 | 0.296 | 2.36 | 14 of 36 | 0.359 |

Facts covered and wrong facts are over each system's answered replies (A0 before 25, A0 fix 26, AAES+ 27). Before the
fix the final reply answered a different question, so it covered no fact of the asked one and could not be wrong
about it; with the fix, it answers the asked question and some answers are wrong or for the wrong group. AAES+ did
not ask first on 3 of the 39 personas.

**Transcripts** (`transcripts.md`): the counseling questions (I07, T14-015, T14-017) and T14-033. T14-033 before:
"I'm an undergraduate student." → an answer about TOPIK scholarships. With the fix, AAES+: "I'm on leave of
absence." → answering "Where do international students apply to return to the Seoul campus?" → no page found
(abstain), so the question is now the right one but retrieval still misses the page.
