# Limitations (running list; every item goes into the report)

## Question set (P5)
- **No human-written questions (PLAYBOOK A28).** The 180 test and dev questions were drafted by Codex from
  page titles and headings only (T14, `labels/topics.jsonl`; no page bodies), then selected and edited by
  Claude Code (`labels/drafts/review.csv`: 161 kept, 19 edited for naturalness or temporal wording, 50
  deleted). None was written by a human. Origins: `agent_draft` 161, `agent_edited` 19
  (`labels/drafts/quota_view.jsonl`).

## Applicability tags (P4)
- The tag audits are automated: Codex wrote the reference and judged disagreements, Codex also wrote the
  tagging rules, and no human validated the audit (PLAYBOOK A14). Final G2b scores: see `Sources/data/DATA.md`.

## Labels (P5, A33 autonomous mode)
- **Nothing is human-verified.** Labels are LLM-annotated (Codex for batches 01-03, Sonnet 5.5 for 04-06),
  LLM-adjudicated (one fresh Opus 5.5 subagent, 47 disputed or flagged rows) and LLM-verified (fresh Opus 5.5
  subagents, every test case and every case flagged by `labeling.checks`). Claims are relative comparisons
  between methods on an LLM-annotated test set, not absolute accuracy figures.
- The same model family (Claude) annotated batches 04-06, adjudicated and verified; Opus 5.5 also served as
  second annotator on the agreement subset. Independence is between contexts, not between vendors, except for
  Codex batches 01-03.
- Agreement before adjudication (κ answerability): Codex vs Opus 0.56, Sonnet vs Opus 0.43 (collapsed 0.55 and
  0.71) (`Report/results/labels/`).
- 12 of 180 cases are excluded (`Sources/data/HYU/labels/excluded.jsonl`): 1 at adjudication, 11 at
  verification, mostly because the right label needs gold spans the primary label lacked (missing campus branch).
  The split was made before dropping them, so dev has 47 cases and test 121.
- The verification sheet first lacked the session history; the 16 rows with history were re-verified with it
  (the second verdict replaced the first).
- Guideline gaps the adjudicator reported: the 11.1 reading of the ERICA NHI "governed by the Ministry …
  contact the NHI Customer Center" line (4 cases labelled unanswerable), the still-open 10.4.1 (campus unstated,
  Seoul-only evidence: treated as no branch), same-procedure lists of two values (answer, conditional
  acceptable), and contradictory ERICA HIEA eligibility text (caveat).
- G2b (tag quality on a fresh sample) last failed on degree_level, student_type and visa (r4 audit); the r5
  tagger round was not re-audited by a human. AAES results depend on these tags.

- **Stated profile not always in the text (dev-01).** At least one dev case (T14-203) has `campus` in its
  `stated_profile` although neither the question nor the history names a campus. The system sees only the text,
  so such a case counts against every profile-aware method. Labels are frozen; this was found on dev and the
  test split was not inspected for it.

## A34 (2026-11-14)

- Evaluator v1 scored every non-AAES reply as answer or abstain from the generation outcome. Evaluator v2 reads the
  reply text; it was frozen on dev outputs, but designed after the v1 test results were known. Validation: one
  blind LLM annotator on 100 dev replies (kappa 0.899), no human.
- The saved raw records keep no AAES trace, so CLARIFY reasons come from a dev replay of A0's decision step.
- The automatic G5 gate checked completion, not whether the code matched the design (branch = distinct answer
  values), so the mismatch reached the test run although dev already showed A0 below B0.
- The planning chat's `section9_course_mapping.md` never reached this session; draft section 9 has a TODO.
