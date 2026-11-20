# Privacy and data check (deck v4 Task 5, 2026-11-16)

Facts only, from the code and the running app on the Mac.

## What the app stores

| What | Where | How long | Can the user see / clear it? |
|---|---|---|---|
| Chat messages and the remembered profile | Browser memory only (React state in `useChat.ts`); never written to disk by the frontend | Until **Forget my details**, **New conversation**, or a page reload | Yes. The remembered details are shown above the input ("Remembered about you: …"). **Forget my details** stops sending the earlier turns (added in Task 1, test in `app.test.tsx`); New conversation clears the chat. |
| Trace of every chat request: question, earlier turns (`history`), profile from step 1, retrieved passages, answer | Collection `traces` in the default MongoDB database (`hyu_compass`) and each index revision with a manifest (`hyu_bench_<index_id>`), including the tagged HYU index (Docker volume `hyu-compass_mongodb_data`) | MongoDB TTL expiry defaults to 30 days; set `TRACE_TTL_DAYS` to change it. MongoDB removes expired traces asynchronously. | Visible in the Execution tab; `GET /api/traces/{request_id}` reads the default store. In Help, **Delete stored history** shows the total across all chat-capable stores and asks for confirmation before calling `DELETE /api/traces`. The count and delete endpoints accept localhost clients only. |
| Evaluation runs | `Report/results/…` and `Report/slides/deck_v4/…` (questions written by the team, never by real students) | In the repository | Not personal data. |
| Backend log | `Sources/.run/backend.log` | Until `./stop.sh`/manual delete (overwritten on start) | Holds request lines (`POST /api/chat 200`), not the question text (0 matches of question words). |
| Preferences | Browser `localStorage`: theme, "help closed", the pipeline configuration | Until the browser's site data is cleared | Not personal. |

## Does anything leave the Mac?

- Questions, history and answers: **no**. Generation runs on the local Ollama (`127.0.0.1:11434`), and search on the local
  MongoDB and Qdrant (Docker).
- The page loads two fonts from Google Fonts (`Sources/frontend/index.html`): the browser contacts Google, but no chat
  content is sent.
- On first start the embedding model and the cross-encoder are downloaded from Hugging Face (the log warns about
  "unauthenticated requests"): model files only, no user text.

## Does the index hold personal data?

Scan of the 1,867 chunks of index r5 (`Sources/scripts/deck_v4_privacy.py` → `privacy_scan.json`):

| Pattern | Matches | Chunks | Note |
|---|---|---|---|
| Unmasked e-mail address | 0 | 0 | All e-mails were masked at crawl time |
| Masked e-mail (`[email]`) | 1,424 | 255 | The mask itself |
| Phone number | 292 | 158 | Office numbers of university departments (e.g. `+8*-2-2***-1***`) |
| Title + capitalised name (Prof., Dr., Mr., Director …) | 23 | 20 | Public staff names on official pages (e.g. `D*. J***`); candidates, not confirmed |
| "My name is …" in text | 0 | 0 | One ERICA welcome page names the Vice President in a section heading (public official page) |

No student data is indexed; the pages are the public English pages of the two international offices. Staff
directories were not crawled (crawler rule), but office phone numbers and a few staff names on notices remain.

## Trace retention (T41, T41b)

At startup, the backend finds the default database and every index revision with a manifest, including smoke
revisions. It creates a TTL index on the BSON Date `expires_from` in each store. It updates an existing index's
expiry with `collMod`, preserving the collection. For older traces, it backfills `expires_from` from `created_at`
(an ISO string or a BSON Date). It leaves unparseable dates untouched and logs their count; these traces can still
be deleted with **Delete stored history**. The existing `created_at` field stays unchanged.

`GET /api/traces` returns `count`, the total across those stores, and `stores`, a count for each index ID. Both
counting and deletion discover the stores on each request, so they also include revisions added after startup.
Revisions added while the backend is running receive TTL setup at the next backend startup.
The Help panel asks "Delete all N stored request traces on this computer? This cannot be undone." Delete removes
traces from every discovered store and reports the total deleted; Cancel keeps them. Documents, chunks, manifests
and indexes remain. The current conversation stays in browser memory until New conversation or a reload.

## Gaps (not fixed)

- `GET /api/traces/{id}` has no authentication (acceptable on localhost; not for a shared deployment).
