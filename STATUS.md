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
