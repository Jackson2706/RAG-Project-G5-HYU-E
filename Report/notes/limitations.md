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
