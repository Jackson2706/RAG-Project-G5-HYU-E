# T09b — Snapshot index: LLM errors, reproducible tag cache, stronger VERIFY
Owner: Codex · Reviewer: Claude Code · Phase: P4

Goal: Fix the accepted T09 review findings 1 and 2, and harden the tag cache and VERIFY before the
human runs the real ingest.

Read first:
- AGENTS.md;
- `Sources/docs/agent_tasks/T09.result.md`;
- `Sources/backend/app/rag/snapshot.py`;
- `Sources/scripts/ingest_snapshot.py`;
- `Sources/backend/app/rag/blocks/ingestion/metadata_extraction/applicability_extractor.py`
  (`tag_chunks`, `_apply_llm_fallback`);
- `Sources/backend/app/rag/pipeline.py` (`_tag_chunks`);
- `Sources/backend/tests/test_snapshot_index.py`.

Allowed write paths: the six files above, `Sources/docs/aaes_spec.md` (Index section),
`Sources/docs/agent_tasks/T09b.result.md`.

Do not touch:
- `Report/`;
- the vocabulary and `validate` in `applicability.py`;
- `tests/test_applicability.py` and its fixture;
- the default index.

Spec:
1. **LLM errors.**
   - A failed LLM call is any exception: Ollama down, timeout, or model missing. Count it as
     `llm_errors`, separately from rejections.
   - A failed call is never written to the cache, so a `--force` re-run retries it.
   - VERIFY gets a check `llm_errors_zero`; the index stays `built` unless it is 0.
2. **Offset test** (`test_snapshot_row_becomes_english_sections_with_exact_offsets`).
   - Compare `full_text[span.start:span.end]` for every lookup span with the expected span texts,
     in order: equality, not `in`.
   - Make sure the test fails if every offset is shifted by one. Check this by hand once and say so
     in the result note.
3. **Reproducible cache key and LLM settings.**
   - Cache key = sha256(model digest + "\n" + `TAG_PROMPT_VERSION` + "\n" + sha256(chunk text)).
     - Add `TAG_PROMPT_VERSION = "v1"` next to the prompt in the extractor. Bump it whenever the
       prompt text changes.
     - Get the digest from `pick_model` (Ollama `/api/tags`).
     - Resolve the model, and its digest, once before the first cache lookup. A missing digest is an
       error, never an empty key part.
   - The LLM settings are fixed: temperature 0, seed 42, thinking off (`think="off"`).
   - Record in the manifest `applicability.llm`: model, digest, `prompt_version`, temperature,
     seed, `num_ctx`, thinking, and the cache file path.
   - With `--no-llm`, nothing is resolved and `llm.enabled` is false.
4. **Real-data VERIFY checks.**
   - (a) **Span text.** While building, store on each MongoDB chunk `source_spans`: the snapshot
     `[char_start, char_end]` of every span it covers. Add the snapshot offsets to `SpanInfo` for
     this.
     - VERIFY re-reads `documents.jsonl` and, for every chunk, joins
       `snapshot_text[s:e].strip()` of its `source_spans` with "\n".
     - The chunk text must equal that join when the chunk covers whole spans, and must be a
       substring of it when the chunk is a window inside one long span.
     - Report `span_text_mismatches` (count, plus the first 5 chunk IDs). The check
       `span_text_matches` passes only at 0.
   - (b) **Token count.** Count the bge tokens of the embedded text (header + "\n" + text) + 2 with
     the index's embedder. `max_embedded_tokens ≤ 512` and `truncated_by_embedder == 0` already
     exist; keep them, and make sure they use exactly the text that was embedded.
5. **Manifest counts** (`applicability`):
   - `tagged_by_rule`, `tagged_by_llm`;
   - `llm_rejected` (vocabulary validation or substring check failed; a dict by reason, plus the
     total);
   - `llm_errors`, `llm_called`, `llm_cache_hits`;
   - `unconditioned`: chunks with no constraints after rules and LLM.

   Rejections are reported only. Only `llm_errors` and the VERIFY checks block PUBLISH. Copy these
   counts into the VERIFY report (`Report/results/index_reports/<id>.json/.md`).
6. **Review finding 3** stays as it is. Add `# shortcut: class-level cache path; one ingest per
   process, pass it per call if two ever share a process` at the `cache_path` class attribute.

Tests that must pass (add these):
- `llm_errors`: a fake LLM that raises gives `llm_errors == 1`, nothing in the cache file, and
  `evaluate_checks` returns `built` with `llm_errors=1`;
- cache key: the same chunk with a different digest or prompt version misses the cache, and the
  same triple hits it;
- the offset test as in item 2;
- span text: `evaluate_checks` fails when `span_text_mismatches=1`, plus one unit test of the
  join/substring rule (whole spans and a window);
- all existing suites: backend 132, evaluation + crawler 87.

Verify with:
```
cd Sources/backend && pytest -q
cd Sources && pytest -q evaluation/tests crawler/tests
python -m evaluation.runner --suite all --dry-run
python scripts/ingest_snapshot.py --snapshot hyu-20261110-97dc1269 --index-id hyu_20261110_97dc1269_r1 --dry-run
```

Human runs: the ingest, after Claude Code's review.

Done when: AGENTS.md Definition of done is met, and `T09b.result.md` lists the changes, the
shift-by-one check from item 2, and the dry-run output.
