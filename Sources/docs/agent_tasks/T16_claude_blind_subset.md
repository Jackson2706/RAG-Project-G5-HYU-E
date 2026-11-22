# T16 — Claude Code blind second annotation (54-case subset)
Owner: Claude Code, in a fresh context (subagent) · Reviewer: humans adjudicate (T17) · Phase: P5 (A19, A26–A28)

Goal: Annotate the stratified ~30% subset (`labels/subset_ids.txt`, 54 of 180 cases, 30% of each
slice × campus target, seed 13) independently of Codex, so T17 can measure agreement.
Part 1 (`annotation_input/t16_part1.jsonl`, 29 cases from batches 01-03) first; part 2
(`annotation_input/t16_part2.jsonl`, 25 cases) after Codex finishes batches 04-06.

Selection (orchestrator only, from `drafts/quota_view.jsonl`, which the annotator never sees): per stratum,
sort ids, `random.Random(13).shuffle`, stable-sort batches 01-03 first, take the allocation
unconditional 11/8, conditional 8/6, temporal 4/1, negative 7/4, multi_session 3/2 (Seoul/ERICA; largest remainder).

Read ONLY: `Sources/data/HYU/labels/GUIDELINES.md` v1.0; `Sources/data/HYU/labels/questions.jsonl`; the part
input file (question, session history, the persona's `gold_profile`; no hints); the snapshot through
`python -m labeling.search` (run from `Sources/`) and by reading the spans it returns.

Do NOT open: `labels/annot_codex/`, `labels/drafts/`, `labels/personas.json`, `Report/`, the PLAYBOOK, STATUS,
task result notes, any index, the backend, or any system output.

Write ONLY: `Sources/data/HYU/labels/annot_claude/part_1.jsonl` (then `part_2.jsonl`) and
`Sources/data/HYU/labels/annot_claude/NOTES.md`. Row format as in T15 (all judgement fields, `case_version`
"1.0", `snapshot_id`, `annotator: "claude-code:claude-opus-5-5"`, no slice/origin/split).

Check: `cd Sources && python -m labeling.validate data/HYU/labels/annot_claude/part_N.jsonl --annotation` exits 0.

## v1.1 run (PLAYBOOK A30, 2026-11-12)
- The rulebook is GUIDELINES.md **v1.1**; section 9 wins over sections 1-8. Every row has `case_version: "1.1"`.
- Re-label part 1 from scratch: do not open the old `annot_claude/part_1.jsonl` (or the old NOTES.md); overwrite both.
- Then do part 2 (`annotation_input/t16_part2.jsonl`) into `annot_claude/part_2.jsonl`.
- Validate each part file (exit 0) before moving on. NOTES.md: per part, done / not done, hard cases, v1.1 questions.
