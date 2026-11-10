# T09 — HYU snapshot index revision with applicability tags (BUILD → VERIFY → PUBLISH)
Owner: Codex · Reviewer: Claude Code · Phase: P4

Goal: Ingest the frozen snapshot `hyu-20261110-97dc1269` (362 docs) as a NEW index revision. Each
chunk carries a `ChunkCondition` from the T08 tagger: the full tags go into the MongoDB chunk
metadata, and a compact copy of the filterable fields goes into the Qdrant payload. The app's
default index (the synthetic fixture) stays untouched.

Read first:
- AGENTS.md, and PLAYBOOK "Amendments" (A4 and the P4 additions);
- `Sources/backend/app/database.py` (index revisions `hyu_bench_<id>` / `bench_<id>`, `for_index`, manifests);
- `Sources/backend/app/rag/pipeline.py` (`index_documents`, the manifest fields, the truncation check);
- the chunking block `section_chunker.py`;
- `vector_indexing/qdrant_indexer.py` and `Database.replace_index`;
- `metadata_extraction/applicability_extractor.py` (`tag_chunks`, LLM fallback);
- `Sources/scripts/ingest.py`;
- one row of `Report/data/HYU/snapshots/hyu-20261110-97dc1269/documents.jsonl`. Its fields:
  - `title`, `site`, `campus`, `source_uri`, `post_date`, `superseded_by`;
  - `spans`: kinds heading / paragraph / table_row / list_item / attachment, with
    `char_start`/`char_end` into `text`;
  - `attachments`, `lang_coverage`.

Allowed write paths:
- new `Sources/backend/app/rag/snapshot.py` (snapshot rows → ParsedDocument + span lookup);
- `Sources/backend/app/rag/pipeline.py` (`index_documents`: optional per-chunk tagging, extra
  manifest fields);
- `Sources/backend/app/database.py` and `vector_indexing/qdrant_indexer.py` (chunk-level payload
  fields only);
- `metadata_extraction/applicability_extractor.py` (only the LLM cache and the cue filter below);
- new `Sources/scripts/ingest_snapshot.py`;
- new tests under `Sources/backend/tests/`;
- `Sources/docs/02_RAG_ARCHITECTURE.md`, `Sources/docs/aaes_spec.md` (the index section);
- `Sources/docs/agent_tasks/T09.result.md`.

Do not touch:
- `Report/data/**` (read only);
- the default index and its collections;
- `Sources/scripts/ingest.py` behaviour;
- the vocabulary in `applicability.py`;
- the T08 tests and their fixture.

Spec:
1. **Snapshot → documents** (`snapshot.py`, `load_snapshot(snapshot_id) -> list[ParsedDocument]`).
   - **Sections:** a new Section starts at each `heading` span. The other spans are appended to the
     current section, one per line, so `full_text()` offsets map back to the spans.
   - **English-only headers (A4).** A heading used as a section header, or as the doc title in the
     embedding text, must have no Hangul (U+AC00–U+D7A3, U+1100–U+11FF, U+3130–U+318F). Otherwise
     fall back to the nearest earlier English heading in the document, then to the first English
     heading, then to None.
     - Strip Seoul's `/ … /` wrapper from titles.
     - A Korean-only title falls back the same way. Keep the original title in
       `declared_metadata["title_original"]`.
   - **declared_metadata** holds `site`, `campus`, `post_date`, `superseded_by`, `snapshot_id`,
     `source_sha256`.
   - **Span lookup:** keep a per-document list of `(start, end, kind, heading_path)`, so a chunk can
     ask which span kinds it covers and what its heading path is.
2. **Chunking.**
   - Use `section_tokens` with `chunk_size=320`, `chunk_overlap=48`, measured with the bge tokenizer
     (the configured embedder; `BAAI/bge-small-en-v1.5`).
   - A table row is never split across chunks unless the row alone exceeds 320 tokens. When a long
     section is windowed, the window starts on a row boundary where possible, and the chunk repeats
     the section heading via `section`.
   - The embedded text is `"{english header}\n{chunk text}"`, as today.
3. **Tagging (per chunk).**
   - Build the T08 chunk dict from the chunk and the span lookup:
     - `kind`: `table_row` if every covered span is a table row, else the single kind, else `mixed`;
     - `heading_path` from the lookup;
     - the rest from `declared_metadata`.
   - Call `ApplicabilityExtractor.tag_chunks`, then `condition.validate(chunk_text)` for every chunk.
     A chunk that fails validation is an error, never silently stored.
   - MongoDB chunk document: add `applicability: condition.to_dict()` and
     `vocabulary_version`.
   - Qdrant payload: add `condition.to_payload()` (the `app_*` keys) next to the existing
     `chunk_id`/`doc_id`/doc metadata. These are chunk-level fields; nothing else in the payload
     changes.
   - **LLM fallback: cost control.**
     - Call the LLM only for chunks where the rules found no constraints AND the text contains a
       cue. A small regex list in the extractor: eligib, applicants?, only, must, required,
       students? (who|with|in), undergraduate, graduate, exchange, visa, TOPIK, enrolled, leave of
       absence, semester, year.
     - Cache LLM answers on disk by `sha256(model + prompt)` in `Report/data/HYU/cache/llm_tags.jsonl`.
       That path is gitignored, and Claude Code adds the rule. A re-run then makes no new calls.
     - The model is `qwen3.5:4b` (auxiliary role). Record model name, digest, temperature,
       `num_ctx`, seed and thinking=off in the index manifest under `applicability`, together with
       the counts: chunks, rule-tagged, LLM-called, LLM-accepted, LLM-rejected (by reason) and
       cache hits.
   - `tag_chunks` runs its own event loop, so the script calls it synchronously, outside any running
     loop. Do not call it from FastAPI handlers.
4. **BUILD → VERIFY → PUBLISH** (`scripts/ingest_snapshot.py`).
   ```
   python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r1 [--no-llm] [--dry-run] [--publish]
   ```
   - **`--dry-run`:** no databases and no Ollama. Load, chunk, tag with rules only. Print:
     - docs, chunks, and max/median tokens of the embedded text;
     - chunks over 512 tokens;
     - how many chunks WOULD call the LLM;
     - the attribute-frequency table.

     Write nothing. The agent may run this.
   - **BUILD:** refuse `--index-id default`, and refuse an id that already has a manifest unless
     `--force`. Build with `index_documents` into `services.db.for_index(index_id)`. Record the
     manifest as usual plus `snapshot_id`, the snapshot manifest sha256, `status: "built"` and the
     `applicability` block.
   - **VERIFY:** re-read MongoDB and Qdrant and check each item below. Each check is pass/fail.
     - Mongo documents = 362, and Mongo chunks = Qdrant points;
     - vector dimension = 384;
     - chunk IDs are unique and every Qdrant point ID has a Mongo chunk;
     - max embedded tokens ≤ 512 and `truncated_by_embedder == 0`;
     - every chunk has a validating `applicability` and every point has `app_scope` and `app_campus`;
     - 0 unmasked e-mails in chunk text (the crawler's `EMAIL_RE`, ignoring the `[email]` mask);
     - 0 Hangul in any embedded header;
     - the default index's document, chunk and vector counts are the same as before BUILD (record
       them before BUILD).

     Write the report to `Report/results/index_reports/<index_id>.json` and `.md`. Set
     `status: "verified"` only if all checks pass.
   - **PUBLISH (`--publish`):** only from `status: "verified"`. Set `status: "published"` and
     `published_at` in the manifest. Nothing is copied or renamed. The index is then selectable
     through the existing `index_id` request field and `GET /api/indexes`.
5. **Docs.** Add the snapshot-index flow, the payload keys and the verification checks to
   `02_RAG_ARCHITECTURE.md`, and a short "Index" section to `aaes_spec.md`.

Tests that must pass (new, offline: no Mongo, Qdrant or Ollama):
- `snapshot.py`:
  - one synthetic snapshot row built in the real structure (A1) with a Korean heading, a `/ … /`
    title, and a table section;
  - sections and offsets map back to the spans;
  - the Korean heading falls back to the previous English heading;
  - the title wrapper is stripped.
- Span lookup → chunk `kind` and `heading_path`: one table-only chunk (`table_row`) and one mixed
  chunk.
- A real-data test on the committed snapshot, skipped when the snapshot or the cached bge tokenizer
  is absent:
  - every document loads;
  - no embedded header contains Hangul;
  - no chunk at 320/48 has more than 512 embedded tokens.
- The cue filter:
  - a chunk with no rule constraints and no cue → no LLM call;
  - with a cue → one call, and a second run hits the cache (fake LLM, `tmp_path` cache).
- The payload: the Qdrant point payload for a tagged chunk has the `app_*` keys of `to_payload()`.
  Use the existing in-memory or fake Qdrant pattern from the backend tests.
- VERIFY logic on fake counts: one failing check means status stays `built`.
- All existing suites still pass: backend 119, evaluation + crawler 87.

Verify with:
```
cd Sources/backend && pytest -q
cd Sources && pytest -q evaluation/tests crawler/tests
python -m evaluation.runner --suite all --dry-run
python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r1 --dry-run
```
Paste the dry-run output into `T09.result.md`.

Human runs (needs MongoDB, Qdrant and Ollama; the agent must NOT run these):
```
cd Sources && conda activate RAG && ./start.sh
caffeinate -i python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r1
# then, once the verification report is all pass:
python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r1 --publish
```

Done when: AGENTS.md Definition of done is met (no UI change), and `T09.result.md` has:
- every file changed;
- the dry-run output;
- the expected number of LLM calls;
- the human commands.
