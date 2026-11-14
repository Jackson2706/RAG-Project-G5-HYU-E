# Demo script (about 8 minutes)

All cases are from the frozen **dev** split, never test. The behaviour noted for each case comes from
`Report/results/dev-02/hyu_dev_v2_per_case.csv` (evaluator v2) and, for A0's branch reasons,
`Report/results/dev-02/a0_decisions_dev.jsonl`. The demo shows *how* the methods behave. Every claim about which
method is better comes from `Report/results/test-final` and is on the slides, not in the demo. Labels are
LLM-annotated and LLM-verified (A33).

## Warm-up checklist (10 minutes before)

1. `cd Sources && ./start.sh` (Docker: MongoDB + Qdrant, backend, frontend). No internet needed.
2. **Switch the index to the frozen HYU revision r5 (`hyu_20261110_97dc1269_r5`) in the Configuration tab.** The UI
   opens on the sample index.
3. Close Chrome tabs and other heavy apps. The 4B model needs most of the 16 GB, and on 2026-11-14 it was swapped
   out while Chrome was open.
4. Load `qwen3.5:4b` with one throwaway question (the first call takes about 20 s, later calls 5-15 s).
5. Check that every group shows in the preset list. G1 and A2 are disabled with "needs a demo case" until a demo
   case is picked.
6. Use at most 3 compare columns (runs are sequential).
7. Backup: the dev-02 per-case table and a screen recording, in case a live run hangs.

## Script

| # | Time | Dev case | Columns | What to point at |
|---|---|---|---|---|
| 1 | 0:00-2:00 | (a) T14-132 "Which insurance rules apply to me?" | B0 · A0 | B0 lists the rules of one page as if all of them applied to this student (scored *answer*; the label wants a question or a conditional answer). A0 gives a conditional answer by campus and academic status, which the label accepts. Open A0's Execution tab: profile (campus and status missing) → applicability labels → branch table → CONDITIONAL. The Seoul branch has no applicable chunk, so it says "ask the OIA office". |
| 2 | 2:00-4:00 | (b) T14-015 "Can international researchers get counseling in English?" | B0 · A0 | Campus over-clarification. B0 answers "yes", and the label expects an answer. A0 asks "Seoul or ERICA?". In A0's Execution tab, the branches are campus and degree level, and one campus row has no applicable chunk. The reason is `different_procedures`, because the differing chunks come from more than one document. AAES branches on *which chunks apply*, not on whether the answer differs, and it asks before checking that the evidence answers at all. This is the main failure on the results slide. |
| 3 | 4:00-6:00 | (c) T14-017 "How do I book the international student counseling program?" | R16 · A0 | R16 is prompted to give per-case answers or ask, but it gives one answer (apply online through the link) without asking which campus. A0 asks for the campus, which the label accepts (it expects a conditional answer and also accepts a question). Same question, same retrieval family: the difference is the explicit branch test. |
| 4 | 6:00-7:00 | T14-058 "When is the ERICA library open?" | R16 · A0 | The honest other side: the campus is in the question and R16 simply answers. A0 still splits by student type and writes two identical cases. The over-triggering, again. |
| 5 | 7:00-8:00 | any column | Execution tab | Every AAES step's typed input and output. G1 (gold evidence) is the upper bracket on a demo case (pick T14-132 from the demo-case list). |

Spare cases: T14-184 (the corpus cannot answer; A0 abstains), T14-209 (multi-session; A2 with the labelled profile
vs A0).

## If something fails

- A column hangs for more than 60 s: stop it and show the dev-02 row for that case instead.
- Ollama error: the column shows the reason. Restart with `ollama serve` and re-run that one column.
- Live output differs from dev-02: say so. Generation is seeded (seed 42, temperature 0), but the index and model
  version on the laptop must match the run manifest.
