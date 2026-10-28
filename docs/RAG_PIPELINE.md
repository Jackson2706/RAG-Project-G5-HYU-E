# The RAG Pipeline, Stage by Stage

This document explains every stage of HYU Compass from first principles and points to the code.
**Implemented** means the code runs when selected; **planned** means it is registered (visible
in the UI, documented) but validation refuses to execute it. Example values come from real runs on
the synthetic sample corpus (`data/samples/`, index revision `c384769ff7b0`).

- [Part 1 — Fundamentals](#part-1--fundamentals)
- [Part 2 — Offline stages](#part-2--offline-stages-ingestion)
- [Part 3 — Online stages](#part-3--online-stages-one-question)
- [Part 4 — Relevance, eligibility, sufficiency, grounding, citation correctness](#part-4--five-different-questions)

---

## Part 1 — Fundamentals

**Tokenization.** Models read *tokens*, not characters or words. BGE uses a WordPiece tokenizer:
`"registration"` may be one token, `"TOPIK"` several. We count chunk sizes with the *same*
tokenizer the embedder uses and keep its **offset mapping** (token → character range), which
lets every chunk be an exact character span of the document.

**Chunking.** Embedding a whole handbook into one vector would average away every specific fact,
and a 512-token model can't even read it. We split documents into chunks of ~256 tokens. Too
small: a rule and its exception separate. Too large: one vector mixes several topics.
Structure-aware chunking follows the document's own sections so a chunk is usually "one
heading and its content".

**Embeddings.** An embedding model maps text to a point in ℝ³⁸⁴ such that texts with similar
meaning are close. Queries and documents use the *same* model, so a question about "credit
limits" lands near the chunk that discusses credit limits even with different wording.

**Cosine similarity.** cos(q, d) = q·d / (‖q‖ ‖d‖) — the angle between vectors. We L2-normalize
all vectors, so cosine = dot product. It measures *semantic closeness*, not truth: a passage that
says "the opposite of X" can score high for a question about X.

**Dense retrieval.** Find the k nearest chunk vectors to the query vector. *Exact* search compares
against every vector (Qdrant local mode always does this). *Approximate* search (HNSW graph in
Qdrant server) is much faster on large collections at a small, tunable recall cost.

**Metadata filtering.** Restrict search to *eligible* documents (e.g. campus = ERICA) **inside**
Qdrant, before ranking, instead of retrieving everything and discarding later (which could leave
fewer than k results).

**BM25.** Classic lexical ranking: reward chunks containing the query's terms, more for rare terms
(IDF), with saturation for repeated terms (k1) and normalization for long chunks (b). Strong on
exact names and codes.

**Hybrid retrieval & RRF.** Dense and lexical retrieval fail differently, so combine them.
Their scores are on incomparable scales, so **Reciprocal Rank Fusion** uses ranks only:
score = Σ 1/(k + rank).

**Cross-encoder reranking (planned).** A bi-encoder (BGE) embeds query and passage separately; a
cross-encoder reads them *together* and scores relevance much more accurately — too slow for the
whole corpus, ideal for re-ordering the top 20.

**Evidence selection & context windows.** The LLM sees only what fits in its context window
(`num_ctx` tokens: system prompt + evidence + question + answer). Selection decides which chunks
go in: de-duplicated, within count and token budgets.

**Temperature.** Generation samples the next token from a probability distribution;
temperature T rescales it (p ∝ exp(logit/T)). Low T → focused; high T → diverse. It changes
*how* the model samples, not *what it knows*.

**Grounding.** An answer is grounded when its claims are supported by the provided evidence.
We instruct the model to use only the sources and to cite them as `[S1]`.

**Abstention.** Saying "I don't know" is a correct output when evidence is missing. Two layers:
the sufficiency gate (no usable evidence → don't call the LLM) and the model's own
`INSUFFICIENT_CONTEXT` reply, both turned into an explicit `insufficient_evidence` outcome.

**Citation verification.** We check each cited marker refers to real selected evidence and that
the stored span re-reads to the exact chunk text. This proves *where* a citation points, not
that the claim is true — that would need claim verification (planned).

---

## Part 2 — Offline stages (ingestion)

Entry point: `backend/app/ingestion/pipeline.py::IngestionPipeline.run`, called by
`scripts/ingest.py` and `POST /api/v1/ingest/local`.

### 1. Document Loading — `local_files` (implemented) · `hyu_website` (planned)
- **Purpose:** find source files, record identity and content hash.
- **Input:** corpus path. **Output:** `SourceFile`s (path, `source_uri`, media type, size, SHA-256) + `LoadIssue`s.
- **Algorithm:** sorted recursive scan; reject unsupported/excluded/oversized/empty files *with a reason*.
- **Code:** `app/ingestion/loaders.py::discover_files`. `doc_id = uuid5(source_uri)`.
- **Failures:** wrong path (`FileNotFoundError`), file types filtered by config.
- **Future:** website loader for approved pages (must respect access controls).

### 2. Parsing & Normalization — `structure_aware`, `basic` (implemented) · `advanced_pdf` (planned)
- **Output:** `ParsedDocument` — normalized `content` and ordered blocks (heading/paragraph/list/table) with section path, page and span.
- **Algorithm:** Markdown (front matter, ATX headings, lists, pipe tables), HTML (BeautifulSoup; h1–h6, p, lists, tables, `<meta>`), TXT (paragraphs), PDF (pypdf per page). Each block is NFC-normalized and joined with blank lines; spans index into that string.
- **Code:** `app/ingestion/parsers.py::parse_file`.
- **Limitation (recorded):** spans refer to the *normalized* text stored in MongoDB, not raw bytes. PDF headings/tables are not detected (a warning is stored on the document).
- **Failures:** scanned PDFs (no text → warning per page), encrypted PDFs, invalid UTF-8 (replaced + warning).

### 3. Chunking — `structure_aware`, `fixed` (implemented) · `recursive`, `semantic` (planned)
- **Output:** `Chunk`s with deterministic `chunk_id`, `section_path`, page range, `source_span`, real `token_count`.
- **Algorithm:** pack same-section blocks up to `chunk_size`; headings attach to their content; tables stand alone; oversize blocks → overlapping token windows; small remainders merge back.
- **Code:** `app/ingestion/chunking.py::chunk_document`.
- **Example:** the sample corpus produces 24 chunks (course registration 7, ERICA housing 5, orientation 6, scholarships 5, student services 1).

### 4. Metadata Extraction — `declared`, `rule_based` (implemented) · `llm` (planned)
- **Output:** document fields (campus, audience, document_type, academic_year, dates, topics) with **provenance** (`declared` / `rule` / `parser` / `configured_default`), chunk keywords and topics.
- **Rule:** unknown stays unknown; values outside the vocabularies are dropped with a warning.
- **Code:** `app/ingestion/metadata.py`. `extracted_facts` has a schema but **no records** until the LLM extractor exists.

### 5. Embedding — `sentence_transformers` (implemented) · `ollama_embed` (planned)
- **Output:** one 384-d normalized vector per chunk (`embedding_text` = heading path + chunk text).
- **Contract:** model ID, revision, dimension, normalization, distance, query instruction (`EmbeddingContract`). Validated shape, dtype and finiteness on every batch.
- **Reuse:** vectors of unchanged chunks are copied from the active revision when the contract matches (a re-ingest after editing one file only embeds that file's new chunks).
- **Code:** `app/services/embeddings.py`.

### 6. Vector Indexing — `qdrant` (implemented)
- **Algorithm:** create `hyu_chunks_<revision_id>`, upsert points (id = `chunk_id`), write MongoDB records, **verify**, then move alias `hyu_chunks_active` atomically. Failure → collection deleted, alias untouched.
- **Code:** `IngestionPipeline` + `verify_revision` in `app/ingestion/pipeline.py`.

---

## Part 3 — Online stages (one question)

Orchestrator: `app/rag/pipeline.py::RAGPipeline.run`. Stage classes: `app/rag/stages.py`.
Every stage records its actual input, output, applied parameters, status and measured duration.

| # | Stage | Implemented methods | Planned |
|---|---|---|---|
| 1 | Query Understanding | passthrough, rule_based | llm |
| 2 | Query Rewriting | — (stage disabled) | llm, multi_query |
| 3 | Constraint Validation | passthrough, deterministic | — |
| 4 | Metadata Filtering | exact | boolean, rule_aware |
| 5 | Dense Retrieval | qdrant_cosine | — |
| 6 | Lexical Retrieval | bm25 | — |
| 7 | Hybrid Fusion | none, rrf, weighted | — |
| 8 | Metadata Enrichment | mongodb_lookup | fact_enrichment |
| 9 | Reranking | — (stage disabled) | cross_encoder, llm, rule_aware |
| 10 | Evidence Selection | top_k, token_budget | diversity |
| 11 | Sufficiency Gate | basic | semantic |
| 12 | Context Builder | standard, structured | — |
| 13 | Generation | ollama_chat | — |
| 14 | Citation Verification | id_span | claim_verification |
| 15 | Response Guard | basic | support_based |

### 1. Query Understanding
- **In:** question. **Out:** `understanding.detected_constraints` (campus, audience, academic_year) and matched rules.
- **rule_based:** regexes over controlled vocabularies (“ERICA”, “Seoul campus”, “international students”, “first-year”…). *Example:* “How do international students apply for a dormitory at ERICA?” → `{campus: ERICA, audience: [international]}`.
- **passthrough:** returns nothing and reports `bypassed`.
- **Failure mode:** over-eager rules (e.g. a word that is a campus in one context but not another). Detected values are only *used* if metadata filtering is enabled.

### 2. Query Rewriting (planned)
Disabled by default; both methods are planned, so enabling the stage is a validation error. The
original question is always preserved in `PipelineContext.question`; the retrieval query is
`PipelineContext.query`.

### 3. Constraint Validation
- **deterministic:** merge configured filter values with detected ones, validate against vocabularies, resolve conflicts (`prefer_configured` or `reject`). Rejection stops the pipeline *before* retrieval with a visible error (Lesson 5's `validation_rejected`).
- **passthrough:** configured values only.
- If metadata filtering is disabled this stage is bypassed.

### 4. Metadata Filtering — `exact`
- **Out:** the compiled Qdrant filter (shown in the trace). Each constraint becomes a `must` clause: value ∈ accepted values **or** field unknown (if `include_unknown`). Campus filters also accept `ALL`; a `freshman` filter also accepts `undergraduate` documents.
- **Failure mode:** stale or missing metadata silently narrowing results — watch Recall in the ablation.

### 5. Dense Retrieval — `qdrant_cosine`
- **In:** query, filter, `top_k`. **Out:** candidates with `dense_score`, `dense_rank`, compact payload; embedding preview (model, dimension, norm, first 8 values — never the full vector).
- **Algorithm:** embed `query_instruction + query` with the *active revision's* embedding contract (a mismatch is an error), search the active alias.
- *Example:* “What documents do I need for the need-based scholarship?” → 10 candidates, top dense score 0.8325 (Scholarship guide › Required Documents), ~12 ms search after warm-up.
- **Failures:** no active index (clear error), Qdrant unreachable.

### 6. Lexical Retrieval — `bm25`
- In-memory BM25 over the active revision's chunks (from MongoDB), rebuilt when the revision changes. Same filter semantics evaluated in Python.
- *Example:* “Can I receive two scholarships in the same semester?” → 10 BM25 candidates for 4 query terms.

### 7. Hybrid Fusion
- `none` forwards the single enabled list (bypassed). `rrf` and `weighted` merge, keeping both per-retriever ranks on every candidate.
- *Example (same question, RRF k = 60):* 14 fused candidates, 6 found by both retrievers; the top candidate had dense rank 1 and lexical rank 2.

### 8. Metadata Enrichment — `mongodb_lookup`
- Batch lookup of chunk text, title, section path, page, span and selected document fields. Candidates whose chunk is missing are dropped and listed (`missing_chunk_ids`) — a sign of an inconsistent index (run `verify_index.py`).

### 9. Reranking (planned)
Disabled → bypassed; candidates pass through in their original order. **No scores are invented.**

### 10. Evidence Selection — `top_k`, `token_budget`
- Walk the ranked list; skip near-duplicates (token-set Jaccard ≥ 0.8); stop at `max_chunks` (and `max_tokens`). Every rejected candidate is listed with its reason.
- *Example:* selected 5 of 10 candidates (257 tokens).

### 11. Evidence Sufficiency Gate — `basic`
- Pass if ≥ `min_evidence_chunks` and (optionally) best dense score ≥ `min_dense_score`. Fail → no prompt is built, the LLM is not called, outcome `insufficient_evidence`. The pass message states explicitly that presence of evidence is not proof of support.

### 12. Context Builder — `standard`, `structured`
- Labels evidence `[S1]…[Sn]` with title › section › page (+ metadata), enforces `max_context_tokens`, builds the system + user messages (prompt text: `app/rag/generation.py::SYSTEM_PROMPT`).

### 13. Generation — `ollama_chat`
- Native `POST /api/chat`, streamed. Model = selected, else `OLLAMA_CHAT_MODEL`, else first installed (never an invented name). Only Ollama `options` are sent; `think: false` is sent only to models with the `thinking` capability, and any reasoning emitted in the content is stripped before streaming.
- **Failures:** Ollama down (connection error), model missing, timeout, reasoning exhausting `num_predict` — all shown as a failed stage; downstream stages stay `pending`.

### 14. Citation Verification — `id_span`
- Parse `[S1]`, `[S1, S2]`, `[S1][S3]`; report valid, invalid (no such source), uncited evidence, unresolved chunks, span failures and sentences-with-citation counts.

### 15. Response Guard — `basic`
- Gate failed or model said `INSUFFICIENT_CONTEXT` → abstention message, outcome `insufficient_evidence` (the evidence is returned as *uncited* retrieved passages). Otherwise remove invalid markers and apply `on_missing_citations` (`warn` | `abstain`).
- *Example:* “Where can I park my car on campus?” → gate passed (5 chunks retrieved), the model replied `INSUFFICIENT_CONTEXT`, final outcome `insufficient_evidence` with no citations.

---

## Part 4 — Five different questions

The pipeline deliberately keeps these apart (they are different fields in the trace):

| Concept | Question it answers | Where it is decided |
|---|---|---|
| Retrieval relevance | Does the passage match the information need? | `dense_score`, `lexical_score`, ranks |
| Eligibility | Does the document apply to this student (campus, audience, year)? | Constraint Validation + Metadata Filtering |
| Evidence sufficiency | Is there enough usable evidence to attempt an answer? | Sufficiency Gate (+ model's `INSUFFICIENT_CONTEXT`) |
| Grounding | Are the generated claims supported by the evidence? | *Not automatically verified* — planned claim verification |
| Citation correctness | Does each citation point to real, correctly located evidence? | Citation Verification (`resolved`, `span_verified`) |

A chunk can be highly relevant yet ineligible (another campus), eligible yet insufficient, and an
answer can carry perfectly resolved citations that still don't support its claim. The UI shows
this by separating **cited sources** from **retrieved but not cited** passages and by labelling
span checks as location checks.
