# T08 — Applicability extractor (rules first, LLM fallback)
Owner: Codex · Reviewer: Claude Code · Phase: P4

Goal: Implement the AAES offline tagger. It tags one chunk with a `ChunkCondition`, stating to whom
the chunk applies. Claude Code wrote the vocabulary, the data class and the tests first, and the
human approved the expected tags. Make `Sources/backend/tests/test_applicability.py` pass without
changing it or its fixture.

Read first:
- AGENTS.md;
- PLAYBOOK "Amendments" (P4 additions) and Appendix C;
- `Sources/backend/app/rag/applicability.py` (do not change the vocabulary);
- `Sources/backend/tests/test_applicability.py` and `tests/fixtures/applicability_chunks.json`
  (read every `note`; they explain the expected tags);
- `app/rag/blocks/ingestion/metadata_extraction/` (base, basic, llm);
- `app/rag/registry.py` (Stage "metadata_extraction", the auxiliary-LLM settings);
- `app/rag/blocks/query_processing/query_rewriting/llm_rewriter.py` (how an auxiliary Ollama call is made).

Allowed write paths:
- new `Sources/backend/app/rag/blocks/ingestion/metadata_extraction/applicability_extractor.py`;
- `Sources/backend/app/rag/registry.py` (one new Method entry);
- `Sources/backend/app/rag/applicability.py`, only to ADD small helpers the tagger needs. The
  vocabulary, the fields and `validate` stay as they are;
- `Sources/docs/04_METHOD_REGISTRY.md`;
- new `Sources/docs/aaes_spec.md`, which documents only the offline tagging rules below;
- `Sources/docs/agent_tasks/T08.result.md`.

Do not touch:
- `Report/`;
- the tests and fixture written by Claude Code;
- the pipeline and ingestion wiring (that is T09);
- presets.

Spec:
1. Add `tag_chunk(chunk: dict, llm: Callable[[str], str] | None = None) -> ChunkCondition`.
   - The input `chunk` has these keys: `doc_id`, `site` (`seoul` or `erica`), `title`,
     `source_uri`, `post_date` (`YYYY-MM-DD` or None), `superseded_by`, `kind` (`table_row`,
     `paragraph`, `list_item`, `heading`, `attachment`, `mixed`), `heading_path` (list[str]) and
     `text`.
   - Table rows are tagged from `heading_path` + text together. The crawler already writes rows as
     `Header: value; Header: value`.
2. **Rules come first.** Use plain regex and keyword tables, readable for beginners, with one small
   function per attribute.
   - **campus:** use the site default (`site_default`). A national rule sets `scope="national"`,
     `campus=["seoul","erica"]` and method `rule`.
   - **National rule:** the chunk states a national rule (visa or immigration law: alien
     registration, residence extension, status change, part-time work permits; NHI enrollment or
     premiums) with no campus-specific procedure.
   - **degree_level** comes from Bachelor's/Undergraduate, Master's, Doctoral/Ph.D., language
     program and non-degree. "Master's/Doctoral" gives both. "Year: N/A" adds no year.
   - **year:** "Year 1-2" → `["1","2"]`, "Year 3-4" → `["3","4"]`.
   - **topik_level:** read the "required Level N" columns together with the O/X column.
     - X means the level is not met → `none` … `N-1`;
     - O means it is met → `N` … `6`;
     - "TOPIK level N or higher" → `N` … `6`.
     - A Korean *standard* pass/fail is NOT a TOPIK level. It becomes a requirement.
   - **visa** codes appear literally (D-2, D-2-5, D-2-8, D-4, D-10, D-10-1 → D-10). In a
     "transferring from X to Y" heading, the constraint is the visa the student holds now (X).
   - **student_type:** "degree students" or "international degree students" → `degree_seeking`.
     Also map exchange, visiting, language program and short-term.
   - **academic_status:** from status words (enrolled, leave of absence, completed coursework,
     expected graduates → graduating, admitted, acceptance). An "Exclusions:" list removes the
     listed statuses; whatever stays is the constraint (C04).
   - **requirements:** short text spans for conditions outside the vocabulary: GPA, attendance,
     money amounts, Korean or English standards, "higher TOPIK score than before".
   - **effective_term:** an explicit "YYYY Spring/Fall Semester", "YYYY-1/2" or a dated "applied
     from <date>" wins. Otherwise use `term_of(post_date)`. Undated pages get None.
   - **superseded_by** comes from the chunk (method `snapshot`).
   - Record `extraction_method[field]` for every field you set. For each rule-found constraint,
     store the matching substring in `evidence` when it is cheap to do so.
3. **The LLM fallback** runs only when `llm` is given AND the rules found no constraints.
   - Prompt: JSON only, listing the vocabulary from `VOCABULARY`.
   - Parse the JSON leniently: take the first `{…}` block, and treat no JSON as no tags.
   - Keep a field only if its values are in the vocabulary AND its evidence quote is an exact
     substring of the chunk text. Drop everything else and record why in `trace_details`.
   - Never raise on bad LLM output.
4. **The block.** Add `ApplicabilityExtractor(BaseMetadataExtractor)`.
   - `extract()` returns the same as `BasicMetadataExtractor`.
   - Add `tag_chunks(chunks: list[dict]) -> list[ChunkCondition]`, which calls `tag_chunk`. When
     the `llm_fallback` param is on, it passes an auxiliary-LLM callable built from
     `self.services.ollama`.
   - Params: `llm_fallback` (bool, default true), `model` (default `qwen3.5:4b`), `temperature` 0,
     `max_tokens`. Copy the auxiliary-LLM settings pattern of the rewriter; thinking stays off.
   - Registry: add `Method("applicability_extractor", "Applicability tags (AAES)", ApplicabilityExtractor, True, "<one line>")`.
     Don't change the default method of the stage.
5. `Sources/docs/aaes_spec.md` covers the offline step only: the vocabulary v0 table, the
   condition format, the rules above in short form, and the LLM-fallback contract. Claude Code
   adds online steps 1–4 later.

Tests that must pass:
- `tests/test_applicability.py`: all 23 tests (Claude Code wrote it first; do not edit it);
- one new small test for the block: `tag_chunks` with `llm_fallback=False` on two fixture chunks,
  and the registry validates the new method;
- all existing suites: backend 95 + new, evaluation, crawler.

Verify with:
```
cd Sources/backend && pytest -q
cd Sources && pytest -q evaluation/tests crawler/tests
python -m evaluation.runner --suite all --dry-run
```
No Ollama calls: the tests use fake LLMs.

Human runs: nothing (T09 runs it on the whole snapshot).

Done when: AGENTS.md Definition of done is met (no UI change), and `T08.result.md` lists each rule
and the fixture case it serves, and anything left to the LLM fallback.
