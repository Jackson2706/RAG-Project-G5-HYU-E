# Demo script (about 8 minutes)

All cases are from the frozen **dev** split, never test. The behaviour noted for each case comes from
`Report/results/dev-03/hyu_dev_v2_per_case.csv` (evaluator v2) and, for A0's branch reasons,
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
7. Backup: the dev-03 per-case table and a screen recording, in case a live run hangs.

## Script

Compare mode with three columns, **B0 | R16 | A0**, on dev cases only. The case cards with the full replies and the
evidence are in `case_examples.md`. Behaviour notes are from `Report/results/dev-03/` (evaluator v2).

| # | Time | Dev case | What to point at |
|---|---|---|---|
| 1 | 0:00-2:30 | T14-132 "Which insurance rules apply to me?" | B0 lists rules from one page with no campus condition. R16 and A0 both give conditional answers. Then open **A0's Execution tab**: profile (campus and status missing) → applicability labels → the **branch table** (Seoul rows have no applicable chunk, ERICA rows do) → CONDITIONAL. The empty Seoul branch is why A0 says "ask the OIA office" there. |
| 2 | 2:30-4:30 | T14-120 "Does my insurance change after my visa switches from D-4 to D-2?" | B0 and R16 say the evidence has nothing. A0 asks for the degree level, which is the split in the evidence (degree students pay the KRW 25,000 group insurance; language-course students ask their language school). |
| 3 | 4:30-6:00 | T14-042 "Is there a winter school for international students?" (counter-example) | B0 and R16 answer yes. A0 asks "Seoul or ERICA?" although there is one winter school and one answer. This is the over-triggering on the results slide (1 vs 30 on cases the sources do not answer, 81 branching replies for 15 needed). |
| 4 | 6:00-8:00 | any column | The Execution tab shows every AAES step's typed input and output. G1 (gold evidence) is the upper bracket on a demo case (pick T14-132 from the demo-case list). |

Spare cases: T14-184 (the corpus cannot answer; A0 abstains), T14-209 (multi-session; A2 with the labelled profile
vs A0). T14-044 is not used: B0 gives both campus addresses there, so it does not show a B0 failure.

## If something fails

- A column hangs for more than 60 s: stop it and show the dev-03 row for that case instead.
- Ollama error: the column shows the reason. Restart with `ollama serve` and re-run that one column.
- Live output differs from dev-03: say so. Generation is seeded (seed 42, temperature 0), but the index and model
  version on the laptop must match the run manifest.
