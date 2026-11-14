# test-2 (A35 Step 5)

- `drafts.jsonl`: 121 questions by a fresh `claude-code:claude-sonnet-5-5` subagent that read only topics.jsonl,
  personas.json and GUIDELINES.md (no snapshot text, no system outputs), in test-1's slice x campus counts.
  `labeling.drafts check` accepts only `codex:` annotators, so it flags every row's annotator field; the field
  records the real drafter. session_history was converted from turn objects to plain strings for the checker.
- `pool.jsonl`: 117 after dropping 4 near-duplicates of the 230 earlier drafts (content-word Jaccard >= 0.6):
  T2-004, T2-030 (identical), T2-050, T2-064.
- Selection target, 80 cases, test-1 proportions by largest remainder (declared, no over-sampling of branching):
  unconditional seoul 18 / erica 12, conditional 11 / 7, negative 10 / 6, temporal 5 / 3, multi_session 5 / 3.
