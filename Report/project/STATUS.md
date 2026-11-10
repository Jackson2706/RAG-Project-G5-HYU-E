# STATUS
| Date | Phase | Task | State | Note |
|---|---|---|---|---|
| 2026-11-10 | P1 | T01/T02 | specs written | BEFORE state in Sources/docs/agent_tasks/T01.before.md |
| 2026-11-10 | P1 | T01 | complete | Removed 188 old tracked copies after hash verification; T02 will repair path-dependent backend tests. |
| 2026-11-10 | P1 | T02 | complete | Centralized repository paths, repaired moved callers and docs, and restored all path-dependent checks. |
| 2026-11-10 | P1 | G1 | passed | All AFTER checks re-run by Claude Code match BEFORE: 90/22 tests, 108-task dry run, same 2 volumes, compose name hyu-compass, 27 presets, frontend 13 tests, chat answers from Sources/. |
| 2026-11-10 | P2 | T04 | complete | Added the offline-tested resumable crawler, English extraction, deduplication, reports, and frozen snapshot builder. |
| 2026-11-10 | P2 | T05 | trial checked | Trial crawl reviewed by Claude Code; 5 extractor fixes (Seoul widgets, script text, title-only docs, key/value tables, ERICA staff page denied); full crawl pending. |
| 2026-11-10 | P2 | T05 | full crawl checked | Full crawl reviewed (1,423 requests, 59 min); 5 more extractor fixes (e-mail masking, ERICA attachment types, bare-extension files, e-mail-only docs, gallery board); snapshot rebuild pending. |
| 2026-11-10 | P2 | T05 | done | Snapshot hyu-20261110-97dc1269 built and checked: 362 docs (306 Seoul, 56 ERICA), 0 unmasked e-mails; manifest and snapshot committed. |
| 2026-11-10 | P2 | T05R | done | Two-folder layout: data, results, project docs moved under Report/; config paths, .gitignore, docs and README updated; root leftovers cleaned; manifest and snapshot hashes unchanged. |
| 2026-11-10 | P3 | T06/T06b | done | SOURCE.md for 5 benchmark folders; loaders for original SciFact (CC BY 4.0 / ODC-By) and ConditionalQA (BSD-2, research only; 652 docs, 13,072 sections); real-schema fixtures + real-data smoke tests (Amendment A1). |
| 2026-11-10 | P3 | T07 | done | BEIR SciFact test = original dev: 300/300 IDs and texts match; SUPPORT 124, CONTRADICT 64, NEI 112; BEIR qrels = cited docs (300/300), not evidence. A2 branch 1 applies. |
| 2026-11-10 | P4 | T08 | done | Vocabulary v0 + ChunkCondition (Claude Code, tests first, 12 real chunks approved by human); rule-first applicability extractor with validated LLM fallback (Codex). |
| 2026-11-10 | P4 | T08b | done | Claude Code (human-approved, ~20 lines): year ranges with commas, 'graduate' → master+doctoral, statuses in except/excluded clauses are not constraints; 6 tests. |
| 2026-11-10 | P4 | T09 | review | Snapshot index script BUILD/VERIFY/PUBLISH written by Claude Code (Codex at usage limit, human approved); dry run 362 docs, 1,867 chunks, max 344 tokens, 652 LLM candidates; review fixes go to T09b. |
| 2026-11-10 | P4 | T09b | done | Codex: llm_errors block VERIFY and are never cached; cache key = digest + prompt version + text sha; source_spans text check; manifest counts. Claude Code restored the fail-fast model check. Ready for the human ingest. |
| 2026-11-10 | P4 | T09c | done | Claude Code: tag partition (6 buckets, VERIFY sums to chunks), condition_status unknown for refused LLM answers, LLM cue list extended (772 candidates, 400 rule_unconditioned in dry run). |
| 2026-11-10 | P4 | T09d | done | Ingest r1 VERIFY failed as designed (772 llm_errors): Claude Code's preflight bound the Ollama client to a closed event loop. Fixed (separate client), first error now reported; prompt v2 (evidence-object example) cut format refusals 5/12 → 0/30 on live samples; rejected count fixed. Rebuild with --force pending. |
| 2026-11-10 | P4 | T09 | done | Index hyu_20261110_97dc1269_r1 built, verified (15/15) and published by the human: 1,867 chunks; rule_tagged 695, rule_unconditioned 400, llm_tagged 165, llm_unconditioned 581, llm_rejected 26, llm_errors 0. |
| 2026-11-10 | P5 | T11 | draft | Claude Code: Report/data/HYU/labels/GUIDELINES.md v0.1 (vocabulary v0, 8 worked examples from real snapshot passages, national vs campus, temporal); update after G2, team approval at G3. |
| 2026-11-10 | P4 | T10/T10b | done | Codex: labeling.audit_tags sample/score/frequency; Wilson 95% CIs, bucket-weighted recall, OOV/audience columns, LLM-TOPIK floor; formulas checked by hand by Claude Code. Waiting for r2 (TOPIK fix) and torch reinstall. |
| 2026-11-10 | P4 | T09e | done | Claude Code: ordinal TOPIK thresholds (A9) in rules and LLM post-check; all-values LLM answers refused. r2 dry run: rule_tagged 900 (was 695; 290 chunks state 'TOPIK N or above'), LLM candidates 567 (all expected cache hits). torch reinstalled by the human after a deleted libtorch_cpu.dylib. |
| 2026-11-10 | P5 | T12 | done | Codex: labeling search (BM25 over snapshot spans), validate, agreement (kappa, Jaccard, span F1, adjudication sheet), freeze (Claude Code's tests first). No labels produced (A11). |
