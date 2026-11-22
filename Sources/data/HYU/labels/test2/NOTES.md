# test-2 (A35 Step 5)

- `drafts.jsonl`: 121 questions by a fresh `claude-code:claude-sonnet-5-5` subagent that read only topics.jsonl,
  personas.json and GUIDELINES.md (no snapshot text, no system outputs), in test-1's slice x campus counts.
  `labeling.drafts check` accepts only `codex:` annotators, so it flags every row's annotator field; the field
  records the real drafter. session_history was converted from turn objects to plain strings for the checker.
- `pool.jsonl`: 117 after dropping 4 near-duplicates of the 230 earlier drafts (content-word Jaccard >= 0.6):
  T2-004, T2-030 (identical), T2-050, T2-064.
- Selection target, 80 cases, test-1 proportions by largest remainder (declared, no over-sampling of branching):
  unconditional seoul 18 / erica 12, conditional 11 / 7, negative 10 / 6, temporal 5 / 3, multi_session 5 / 3.
- Selection: 80 (fresh Sonnet 5.5 selector, `selected.jsonl`, reasons in `selection_notes.md`).
- Annotation, blind and independent: A = fresh Opus 5.5 (`annot_A/`), B = fresh Sonnet 5.5 (`annot_B/`), 40 + 40 each.
  Agreement before adjudication (`agreement/agreement.md`): kappa answerability 0.773 [0.614, 0.901], expected
  behaviour 0.708 [0.560, 0.829], branch Jaccard 0.859, span F1 0.648; 18 cases disputed.
- Adjudication: fresh Opus 5.5 for the 8 rows built from B; the validator refused Opus on rows built from A (same
  model as annotator A), so a fresh Haiku 5.5 decided those 10 (`adjudication_final.jsonl`). 5 EXCLUDE, all on
  GUIDELINES 10.4 question 1 (campus unstated, only one campus has current evidence).
- Deterministic checks (`violations.jsonl`): 55 violations on 33 cases. Verification by a model other than the
  case's primary annotator (Sonnet 5.5 for 29, Opus 5.5 for 4): 25 keep (false alarms), 8 edited, 0 EXCLUDE.
  The 47 flags left after verification (`violations_after.jsonl`) are the kept false alarms.
- Frozen: 75 cases, `labels/test2.jsonl`, sha256 in `labels/FROZEN_test2.sha256` (f704d968...), before any system
  ran on it. Expected behaviour: answer 41, abstain 20, conditional answer 12, clarify 2 (14 of 75 need branching).
- Left as labelled: T2-079 (negative slice by the drafter, labelled answerable; an ERICA-only fellowship for a Seoul
  persona) and T2-067 (a possible unstated eligibility branch), both flagged by verifiers as worth a second look.
