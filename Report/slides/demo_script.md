# Demo script (P8D T38, about 8 minutes)

Cases: `Sources/data/HYU/labels/demo_cases.jsonl` (9 cases, all from the frozen **dev** split; never test).
The behaviour noted for each case is from `Report/results/dev-01/hyu_dev_per_case.csv`. The live demo shows
*how* the methods behave. Every claim about which method is better comes from `Report/results/test-final`,
on the slides, not from the demo. Labels are LLM-annotated and LLM-verified (A33).

## Warm-up checklist (10 minutes before)

1. `cd Sources && ./start.sh` (Docker: MongoDB + Qdrant, backend, frontend). No internet needed.
2. Confirm the active index is the frozen HYU revision (r5) in the Configuration tab.
3. Load `qwen3.5:4b` with one throwaway question (first call ~20 s, later 5-15 s).
4. Preset list: every group shows. G1 and A2 are disabled with "needs a demo case" until a demo case is picked.
5. Memory presets (M1/M2, A7) are not part of this build (PLAYBOOK A29), so story 5 of Appendix H is skipped.
6. Close other heavy apps; at most 3 compare columns (runs are sequential, 16 GB Mac).
7. Backup: the dev-01 per-case table and the recorded video, if a live run hangs.

## Script

| # | Time | Demo case | Columns | What to point at |
|---|---|---|---|---|
| 1 | 0:00-1:00 | T14-061 "What documents are needed for a part-time work permit?" | B0 · R16 · A0 | All three answer. AAES adds no friction when nothing branches. |
| 2 | 1:00-2:30 | T14-134 "Can I keep doing paid research after changing to D-10?" | B0 · R16 · A0 | B0 answers and cites a passage that does not apply (relevant, not eligible). A0 abstains and refers the student to the OIA office. |
| 3 | 2:30-4:00 | T14-132 "Which insurance rules apply to me?" | A4 · A0 | A4 decides from the wording alone and answers. A0 sees that the evidence splits and gives a conditional answer per case. Open the A0 column's Execution tab: profile → applicability labels → branches with information gain → decision. |
| 4 | 4:00-5:00 | T14-209 (multi-session, applicant at Seoul) | A0 · A2 · R16 | A2 gets the labelled profile and gives the expected conditional answer; A0 abstains. The difference is profile extraction (step 1): this is the oracle-input test. |
| 5 | 5:00-6:00 | T14-184 (a question the corpus cannot answer) | R16 · A0 | R16 answers anyway; A0 abstains. |
| 6 | 6:00-7:00 | T14-015 "Can international researchers get counseling in English?" | B0 · A0 | Honest failure: A0 asks for the campus although both campuses give the same answer. This is the unnecessary-clarification rate on the results slide. |
| 7 | 7:00-8:00 | any column | Execution tab | Every AAES step's typed input and output; G1 (gold evidence) as the upper bracket on the same case. |

Spare cases if time allows: T14-147 (temporal, all answer), T14-081 (applicant, B0 cites an inapplicable page,
A0 abstains), T14-208 (multi-session abstain).

## If something fails

- A column hangs over 60 s: stop, show the dev-01 row for that case instead.
- Ollama error: the column shows the reason; restart with `ollama serve` and re-run one column.
- Live output differs from dev-01: say so; generation is seeded (seed 42, temperature 0), but retrieval and
  model versions on the laptop must match the run manifest.
