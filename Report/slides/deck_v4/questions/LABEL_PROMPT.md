# Labelling prompt for the dev-2 / test-3 questions (deck v4 Task 3)

You are one of two independent labellers. Never open the other labeller's files (labels_A*, labels_B*), any writer
draft (drafts/), candidates.jsonl, Report/results/, or Sources/data/HYU/labels/*.jsonl. Read
Sources/data/HYU/labels/GUIDELINES.md (sections 1-3 and the amendments it points to) first. Do not run any system.
You may search the frozen snapshot read-only from Sources/: `python -m labeling.search "<words>" [--campus seoul|erica]`
(conda env RAG), for example to check whether the other campus has a page on the topic.

Each input line has case_id, question, session_history (earlier user turns), gold_profile (the real student; the
system never sees it) and passages (chunk_id, title, url, section, text) from the official English pages.

For each case decide, from the official pages only:
- expected_behavior: answer | conditional_answer | clarify | abstain (GUIDELINES section 3), from what the student has
  said (question + session_history), not from gold_profile. A rule whose answer differs between values of an
  attribute the student has NOT stated -> conditional_answer (few short branches) or clarify (many branches or very
  different procedures). If only one campus's pages cover the topic and the student's campus is unknown, the answer
  depends on campus (the other campus's branch is a referral). Nothing in the pages answers it -> abstain.
- acceptable_behaviors: every behaviour that would also be fine (includes expected_behavior).
- branch_attributes: vocabulary v1 attributes whose unstated value changes the answer ([] if none).
- stated_profile: only attributes the student said (vocabulary values).
- required_facts: 1-4 short facts a correct reply must contain (for a split: one per branch, e.g. "Seoul: ...").
  For abstain: the office or next step to refer to.
- gold_evidence: chunk_ids (from the passages) that support the answer for gold_profile, or snapshot spans
  {"doc_id", "char_start", "char_end"} from labeling.search. inapplicable_evidence: relevant chunk_ids that apply to
  another group.
- answerability: answerable | partial | unanswerable | external_only | korean_only.
- exclude: true only if the question is unusable (unclear, not about these pages, personal data); give why in notes.
- notes: <= 20 words, only when a call was hard.

Write one JSON object per case, one per line, to the output file you are given:
{"case_id": "N001", "expected_behavior": "...", "acceptable_behaviors": [...], "branch_attributes": [...],
 "stated_profile": {...}, "required_facts": [...], "gold_evidence": [...], "inapplicable_evidence": [...],
 "answerability": "...", "exclude": false, "notes": "", "annotator": "<the exact model identity assigned to you>",
 "origin": "agent_draft"}
Use the same assigned `annotator` value on every row. Do not infer or copy another labeller's identity.
Label every case in your input file. Reply with: cases labelled, counts by expected_behavior, excluded.
