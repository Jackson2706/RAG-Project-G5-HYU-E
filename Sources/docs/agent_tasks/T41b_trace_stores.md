# T41b — Review fix: trace retention and deletion must cover every trace store
Owner: Codex (gpt-6.1-sol) · Reviewer: Claude Code · Follows T41 (read T41_trace_expiry.md and T41.result.md first)

Must-fix review finding [P1]: chats on a tagged HYU index save traces through the index-specific database
(`Database.for_index`), but GET/DELETE /api/traces and the TTL setup only handle the default database. Delete stored
history can report 0 while student questions stay stored.

Allowed write paths: Sources/backend/app/database.py, Sources/backend/app/api.py, Sources/backend/app/main.py (only if
startup must call the new setup), Sources/backend/tests/test_trace_expiry.py, Report/slides/deck_v4/privacy_check.md,
Sources/docs/agent_tasks/T41b.result.md. Do not commit or push; touch nothing else; never drop collections.

Spec: one helper (e.g. `Database.trace_databases()`) that returns the default database plus every index revision the
app can chat with (reuse `list_index_revisions` / `for_index`). TTL setup + backfill runs on each of them at startup;
GET /api/traces returns the summed count (and per-store counts); DELETE /api/traces deletes from each and returns the
summed count. Localhost rule unchanged. Tests (mongomock): a trace saved through `for_index(...)` is counted, expires
(TTL index present on that store) and is deleted; the default store still works; non-localhost still 403.
Verify with: cd Sources/backend && pytest -q
