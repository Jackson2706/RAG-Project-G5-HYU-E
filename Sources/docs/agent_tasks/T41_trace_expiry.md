# T41 — Trace expiry and "Delete stored history"
Owner: Codex (gpt-6.1-sol) · Reviewer: Claude Code · Phase: deck v5 Phase 1

Goal: request traces in MongoDB `hyu_compass.traces` never expire and cannot be deleted (privacy gap in
`Report/slides/deck_v4/privacy_check.md`). Add expiry, a delete endpoint and a UI button.

Read first: AGENTS.md; Sources/backend/app/database.py (traces section, create_indexes); Sources/backend/app/api.py
(`/traces/{request_id}`); Sources/backend/app/config.py; Sources/backend/app/rag/pipeline.py (trace `created_at`, an ISO string);
Sources/frontend/src/components/chat/HelpPanel.tsx and its test; Sources/frontend/src/services/api.ts.

Allowed write paths: Sources/backend/app/database.py, Sources/backend/app/api.py, Sources/backend/app/config.py,
Sources/backend/tests/test_trace_expiry.py (new), Sources/frontend/src/components/chat/HelpPanel.tsx,
Sources/frontend/src/services/api.ts, Sources/frontend/src/test/ (one new or extended test),
Report/slides/deck_v4/privacy_check.md, Sources/docs/agent_tasks/T41.result.md.
Do not touch: anything else; never drop or recreate collections; do not commit or push (.git is read-only for you).

Spec:
- Setting `trace_ttl_days: int = 30` in Settings (env `TRACE_TTL_DAYS`).
- `save_trace` also stores `expires_from: datetime` (UTC, a BSON Date; keep `created_at` unchanged as the ISO string).
- `create_indexes` adds a TTL index on `expires_from` with `expireAfterSeconds = ttl_days * 86400`. If an index with
  another expiry exists, update it with `collMod` instead of dropping data. Backfill: for traces without
  `expires_from`, set it from `created_at` parsed as ISO (string) or the Date itself; leave unparseable ones untouched
  and count them.
- `DELETE /api/traces` deletes every stored trace and returns `{"deleted": n}`. Only allowed when the client is
  localhost (127.0.0.1 / ::1 / "testclient" in tests); otherwise 403.
- Help panel: a "Delete stored history" button. Clicking shows an in-page confirmation ("Delete all N stored request
  traces on this computer? This cannot be undone." with Delete / Cancel); never `window.confirm`. Success shows
  "Deleted N stored traces."; failure shows the error text.
- Tests (mongomock, no Docker): TTL index created with the right seconds; backfill from string and Date;
  DELETE returns the count and empties the collection; non-localhost → 403. Frontend: the button opens the in-page
  confirmation, Cancel calls nothing, Delete calls the API.
- privacy_check.md: replace the "no expiry and no delete button" gap with the new behaviour (default 30 days,
  env TRACE_TTL_DAYS, DELETE /api/traces, the button).

Verify with: cd Sources/backend && pytest -q ; cd Sources/frontend && npm run typecheck && npm test
Human runs: none (Claude Code takes the screenshot u16).
Done when: AGENTS.md Definition of done items 1, 3 (typecheck/test), 5.
