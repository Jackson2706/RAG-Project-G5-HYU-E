# Hyperparameters

Every hyperparameter lives in **one place**: `backend/app/rag/registry.py`. The UI renders
controls from it, the backend validates against it, and the [reference table](#complete-reference)
at the end of this file is generated from it. This document explains what each parameter
does, why you would change it, and what it costs.

**Scopes** — every parameter has one:

| Scope | Changes take effect… | Examples |
|---|---|---|
| `runtime` | on the next question | Top K, temperature, evidence budget |
| `ingestion` | after re-running ingestion (re-parse / re-chunk) | chunk size, overlap, parser options |
| `index` | after building a **new index revision** (new vectors) | embedding model, normalization, distance |

Changing an `ingestion`/`index` parameter in the Configuration tab does nothing until you
click **Index & Documents → Rebuild** (or run `scripts/ingest.py --config …`). The validator
warns when your draft differs from the active index. Nothing ever silently modifies the
active index: a rebuild creates a new revision and only switches after verification.

> Numbers below about "typical" behaviour are qualitative guidance. The only measured
> values in this project are those in [DATABASE_AND_EVALUATION.md](DATABASE_AND_EVALUATION.md#measured-results).

---

## Offline: chunking

### `chunk_size` (Chunking · integer · default 256 tokens · 32–512 · ingestion)

Target number of **tokenizer tokens** per chunk (counted with the BGE tokenizer, so the number
is exact for the embedder). With `structure_aware`, consecutive blocks of the same section are
packed until adding the next block would exceed `chunk_size`.

- **Increase** → more context per passage, fewer chunks, fewer boundary cuts; but each vector
  averages over more topics (a "blurrier" embedding), distractor sentences enter the prompt, and
  each selected chunk consumes more of the evidence budget.
- **Decrease** → sharper matching of specific facts; but a rule and its exception may be split
  across chunks so neither chunk alone supports the answer.
- Latency/memory: more chunks → more vectors to store and slightly slower BM25 build; query
  latency barely changes at course-corpus scale.
- **Experiment:** 128 vs 256 vs 384 with Recall@5 and MRR on `data/eval/sample_questions.jsonl`.
  Note the sample corpus has short sections, so most chunks are already below 256 tokens and
  this parameter mostly matters for long PDFs.

### `chunk_overlap` (integer · default 32 · 0–256 · ingestion)

Tokens shared between consecutive **windows** when a block is longer than `max_chunk_size`
(structure-aware) or for every window (`fixed`). Step = `chunk_size − chunk_overlap`.

- **Increase** → a sentence cut at a boundary appears whole in at least one window; but storage
  grows by roughly `size / (size − overlap)` and near-duplicate chunks compete for Top-K slots
  (Evidence Selection de-duplicates them).
- **Decrease** → no duplication, but boundary information loss.
- Must be smaller than `chunk_size` (validated).

### `min_chunk_size` / `max_chunk_size` (structure-aware only · ingestion)

`min_chunk_size` (default 32): a trailing piece of a section smaller than this is merged into the
previous chunk of the same section, avoiding tiny low-information chunks. `max_chunk_size`
(default 512, the BGE input limit): a single block longer than this is split into overlapping
token windows. Constraint: `min ≤ chunk_size ≤ max`.

### `preserve_headings` (boolean · default true · ingestion)

Prepends the heading path (e.g. `Course Registration Handbook › Credit Limits`) to the text that
is **embedded and BM25-indexed**. The stored chunk text — and therefore the citation span — is
unchanged. Usually helps queries that use section vocabulary ("credit limit") when the body
doesn't repeat it. Turn off to measure the effect.

### `tokenizer_id` (string · default `BAAI/bge-small-en-v1.5` · ingestion)

Which Hugging Face tokenizer counts tokens. Keep it equal to the embedding model so "256 tokens"
means 256 tokens *to the embedder*. Must be a fast tokenizer (offset mappings are required to
keep spans exact).

## Offline: parsing, loading, metadata

- `file_types`, `recursive`, `max_file_mb` (Document Loading): which files are considered.
  Rejected files are **reported**, never silently skipped.
- `preserve_tables` (Parsing): tables become standalone blocks, so the chunker never merges a
  table with prose. Off → tables are treated as paragraphs.
- `normalize_unicode` (Parsing): NFC normalization before spans are computed. Changing it
  changes `version_id` (parser contract) and thus re-chunks everything.
- `detect_topics`, `detect_campus`, `detect_academic_year` (Metadata, rule-based): transparent
  keyword rules. Inferred values are stored with provenance `rule`, never as declared facts.
  `detect_campus` only fires when exactly **one** campus is mentioned.
- `keywords_per_chunk`: most frequent content terms stored per chunk (display/debug; not used for
  ranking).

## Offline: embedding & vector index (scope `index`)

### `model_id`, `model_revision`

The embedding model and its pinned commit. Default `BAAI/bge-small-en-v1.5@5c38ec7c…`
(384 dimensions, English). Changing either produces a different **embedding contract** and
therefore a new collection; vectors from different models are never mixed. The vector size of
the collection is read from the model — it is not a free parameter.

### `normalize` (boolean · default true)

L2-normalizes every vector to unit length. Then cosine similarity = dot product, and scores are
in [−1, 1]. Mathematical intuition: cos(q, d) = q·d / (‖q‖‖d‖); with ‖q‖ = ‖d‖ = 1 only the
angle matters, not vector length. Lesson 3's "mixed contract failure" is what happens when
normalized and unnormalized vectors share a collection.

### `query_instruction`

BGE was trained with an instruction prefix for retrieval **queries**
(`"Represent this sentence for searching relevant passages: "`); documents are encoded without
it. Removing it is a legitimate ablation but changes the contract (new revision).

### `distance` (Cosine · Dot · Euclid)

The collection's similarity function. With normalized vectors all three give the same ranking
(‖q − d‖² = 2 − 2 q·d). Keep Cosine unless you change normalization.

### `hnsw_m`, `hnsw_ef_construct` (server mode only)

HNSW graph construction: `m` = edges per node (higher → better recall, more memory),
`ef_construct` = candidate list while building (higher → better graph, slower build). **Qdrant
local mode ignores these** and always performs exact search.

### `batch_size`, `device`

Speed/memory only; not part of the contract (changing them does not create a new revision).

---

## Online: retrieval

### Dense `top_k` (integer · default 10 · 1–100)

Candidates returned by vector search.

- **Increase** → higher evidence **recall** (the right chunk is more likely somewhere in the
  list); more work for fusion/enrichment; more distractors if evidence selection is loose.
- **Decrease** → faster, fewer distractors, but a relevant chunk ranked 11th is lost before any
  later stage can recover it.
- Dense `top_k` is a *recall* knob; `max_chunks` in Evidence Selection is the *precision* knob.

### `score_threshold` (float · nullable · default none)

Drop candidates below this cosine similarity. **Uncalibrated**: BGE similarities for unrelated
text are often well above 0, and the right value depends on the corpus. A high cosine score does
not prove a passage answers the question. Calibrate with the evaluation set before using it.

### `exact`, `hnsw_ef` (server mode)

`exact = true` scans every vector (ground truth, O(N)). Otherwise HNSW traverses a graph with a
candidate list of size `hnsw_ef`: larger → closer to exact recall, slower. Local mode is always
exact. Lesson 3: exact local search is the correctness oracle for ANN experiments.

### BM25 `top_k`, `k1`, `b`, `remove_stopwords`

Okapi BM25:

score(q, d) = Σₜ IDF(t) · tf(t,d)·(k1+1) / (tf(t,d) + k1·(1 − b + b·|d|/avgdl))

- `k1` (default 1.5) — **term-frequency saturation**. k1 = 0: a term counts once regardless of
  repetition; larger k1: repeated terms keep adding score longer.
- `b` (default 0.75) — **length normalization**. b = 0 ignores chunk length; b = 1 fully divides
  by relative length, penalizing long chunks.
- `remove_stopwords` — drop function words so "How do I…" does not match every chunk.
- BM25 shines on exact terms (codes, names like "TOPIK", "add/drop") where embeddings blur.

### Fusion: `rrf_k`, `dense_weight`, `candidate_limit`

**Reciprocal Rank Fusion:** score(d) = Σᵢ 1 / (k + rankᵢ(d)). Only ranks matter, so BM25 scores
(unbounded) and cosine (≤ 1) can be combined without normalization.

- `rrf_k` (default 60): **small k** → rank 1 dominates (1/61 vs 1/70 at k = 60, but 1/2 vs 1/11 at
  k = 1); **large k** → the curve flattens and agreement between retrievers matters more than
  any single top position.
- **Weighted fusion** min-max normalizes each list to [0, 1] and computes
  w·dense + (1 − w)·lexical. Sensitive to outliers in either list; `dense_weight` = 1 reproduces
  dense-only ordering on the union.
- `candidate_limit`: how many fused candidates continue (more → more MongoDB lookups).

### Metadata filtering parameters

`campus`, `audience`, `document_type`, `academic_year`: equality constraints compiled into a
Qdrant payload filter (and the same predicate for BM25). `use_detected_constraints` applies what
Query Understanding detected. `include_unknown` (default true) keeps documents whose field is
unknown — *unknown is not ineligible*; turning it off makes filters stricter but silently drops
documents with missing metadata (watch Recall). `include_university_wide` keeps `campus = ALL`
documents. Audiences have a small hierarchy: a `freshman` filter also accepts `undergraduate`
documents (see the evaluation write-up for the bug this fixed).

`conflict_policy` (Constraint Validation): when the question says "ERICA" but the configured
filter says SEOUL, either keep the configured value (and record a note) or reject the request.

## Online: evidence & context

### `max_chunks` (default 5) and `max_tokens` (token_budget, default 1200)

How much evidence reaches the prompt. More evidence → better chance the supporting passage is
included; but small models are easily distracted ("lost in the middle"), prompts get slower,
and the model is more tempted to cite loosely related sources. `max_tokens` counts **chunk**
tokens (BGE tokenizer).

### `deduplicate`, `dedup_similarity` (default 0.8)

A candidate whose token-set Jaccard similarity with an already-selected chunk is ≥ threshold is
skipped. Overlapping windows otherwise fill several evidence slots with the same text.
Lower threshold → more aggressive de-duplication (may drop genuinely different passages).

### Sufficiency gate: `min_evidence_chunks`, `min_dense_score`

The gate answers "is there usable evidence at all?". `min_dense_score` (off by default) abstains
when the best cosine similarity is low. It is uncalibrated; tune it on answerable vs unanswerable
questions and report both false-abstention and false-answer rates.

### Context builder: `include_source_metadata`, `max_context_tokens`

Metadata headers help the model cite precisely and mention the campus/audience; they cost
tokens. `max_context_tokens` is a hard cap — evidence is truncated or dropped (and reported in
the trace). Counted with the embedding tokenizer, an approximation of the LLM's tokenizer.

## Online: generation (Ollama `options`)

| Parameter | Intuition | ↑ effect | ↓ effect |
|---|---|---|---|
| `temperature` (0.2) | Divides logits before softmax: p ∝ exp(logit / T). It reshapes the distribution; it does **not** add knowledge or guarantee correctness. | More diverse wording, more risk of drifting from evidence | More deterministic, repetitive; 0 ≈ greedy |
| `top_p` (0.9) | Sample from the smallest token set whose cumulative probability ≥ p | Wider vocabulary | More conservative |
| `top_k` (40) | Sample only from the k most likely tokens | Wider | Narrower |
| `min_p` (0.0) | Drop tokens with p < min_p · p(max) | Fewer unlikely tokens | Off at 0 |
| `repeat_penalty` (1.1) | Penalizes recently generated tokens | Less repetition (may avoid repeating needed terms) | More repetition |
| `num_ctx` (4096) | Tokens the model attends to (prompt + answer) | Room for more evidence; more RAM/VRAM, slower | Prompt may be truncated by Ollama |
| `num_predict` (1024) | Max generated tokens (−1 = unlimited) | Longer answers allowed | Truncated answers |
| `seed` (none) | Fixed RNG seed | Reproducible sampling for experiments | — |
| `stop` | Strings that end generation | — | — |

Application-level (not sent to Ollama): `model`, `stream` (token streaming to the UI) and
`timeout_s`. **Thinking models** (e.g. `qwen3`): the backend requests `think: false`, and because
some models still emit reasoning inside the content, it strips everything up to `</think>`.
That reasoning still consumes `num_predict` tokens — if the budget runs out before the answer,
the stage fails with a clear message rather than showing the reasoning.

## Online: verification & guard

- `require_citations` — flag answers with no valid `[S#]` marker.
- `verify_spans` — re-read `document.content[start:end]` and compare with the chunk text.
- `on_missing_citations` — `warn` (answer + warning) or `abstain` (replace with the abstention
  message). Note: these checks validate **identity and location** of citations, not that the
  claim is entailed by the passage (claim verification is planned).

---

## Complete reference

<!-- REGISTRY-TABLE:START -->

_Generated by `python scripts/export_registry.py` — do not edit by hand._

### Online stages (runtime)

#### Query Understanding (`query_understanding`)

Methods: `passthrough` (implemented), `rule_based` (implemented), `llm` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `rule_based` | `detect_campus` | boolean | true | — | runtime | basic | 'Seoul campus' / 'ERICA' mentions. |
| `rule_based` | `detect_audience` | boolean | true | — | runtime | basic | e.g. 'international student', 'graduate'. |
| `rule_based` | `detect_academic_year` | boolean | true | — | runtime | advanced | '2025 academic year' patterns. |

#### Query Rewriting (`query_rewriting`)

Methods: `llm` (planned), `multi_query` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `llm` | `temperature` | float | 0.0 | 0.0 … 1.0 (step 0.05) | runtime | basic | Sampling temperature for the rewrite. |
| `multi_query` | `num_queries` | integer | 3 | 2.0 … 8.0 (step 1.0) | runtime | basic | Paraphrases to generate. |

#### Constraint Validation (`constraint_validation`)

Methods: `passthrough` (implemented), `deterministic` (implemented)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `deterministic` | `conflict_policy` | enum | prefer_configured | prefer_configured, reject | runtime | basic | What to do when the question mentions a different campus than the configured filter. |

#### Metadata Filtering (`metadata_filtering`)

Methods: `exact` (implemented), `boolean` (planned), `rule_aware` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `exact` | `campus` | enum | any | any, SEOUL, ERICA | runtime | basic | Restrict to one campus. |
| `exact` | `audience` | multi_enum | — | undergraduate, graduate, international, exchange, freshman, all | runtime | basic | Keep documents for any of these audiences. |
| `exact` | `document_type` | enum | any | any, student_guide, regulation, notice, faq, form, handbook | runtime | advanced | Restrict to one document type. |
| `exact` | `academic_year` | string | — | — | runtime | advanced | e.g. 2025 or 2025-2026. Empty = any. |
| `exact` | `use_detected_constraints` | boolean | true | — | runtime | basic | Apply constraints found by Query Understanding. |
| `exact` | `include_unknown` | boolean | true | — | runtime | basic | Keep documents whose field is unknown. |
| `exact` | `include_university_wide` | boolean | true | — | runtime | advanced | Keep campus = ALL documents when filtering by campus. |

#### Dense Retrieval (`dense_retrieval`)

Methods: `qdrant_cosine` (implemented)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `qdrant_cosine` | `top_k` | integer | 10 | 1.0 … 100.0 (step 1.0) | runtime | basic | Candidates returned by vector search. |
| `qdrant_cosine` | `score_threshold` | float | — | 0.0 … 1.0 (step 0.01) | runtime | advanced | Discard candidates below this similarity. Empty = none. Uncalibrated. |
| `qdrant_cosine` | `exact` | boolean | false | — | runtime | advanced | Brute-force search instead of the HNSW graph (always exact in local mode). |
| `qdrant_cosine` | `hnsw_ef` | integer | 128 | 8.0 … 1024.0 (step 8.0) | runtime | advanced | HNSW candidate list size at query time. Higher → better recall, slower. |

#### Lexical Retrieval (`lexical_retrieval`)

Methods: `bm25` (implemented)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `bm25` | `top_k` | integer | 10 | 1.0 … 100.0 (step 1.0) | runtime | basic | Candidates returned by BM25. |
| `bm25` | `k1` | float | 1.5 | 0.0 … 3.0 (step 0.1) | runtime | advanced | How quickly repeated terms stop adding score. |
| `bm25` | `b` | float | 0.75 | 0.0 … 1.0 (step 0.05) | runtime | advanced | 0 = ignore chunk length, 1 = full length normalization. |
| `bm25` | `remove_stopwords` | boolean | true | — | runtime | advanced | Drop common English function words. |

#### Hybrid Fusion (`hybrid_fusion`)

Methods: `none` (implemented), `rrf` (implemented), `weighted` (implemented)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `rrf` | `rrf_k` | integer | 60 | 1.0 … 200.0 (step 1.0) | runtime | basic | Larger k flattens the advantage of top ranks. |
| `rrf` | `candidate_limit` | integer | 20 | 1.0 … 100.0 (step 1.0) | runtime | basic | Fused candidates kept. |
| `weighted` | `dense_weight` | float | 0.5 | 0.0 … 1.0 (step 0.05) | runtime | basic | Weight of the dense score; lexical gets 1 − w. |
| `weighted` | `candidate_limit` | integer | 20 | 1.0 … 100.0 (step 1.0) | runtime | basic | Fused candidates kept. |

#### Metadata Enrichment (`metadata_enrichment`)

Methods: `mongodb_lookup` (implemented), `fact_enrichment` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `mongodb_lookup` | `include_fields` | multi_enum | ["document_type", "campus", "audience… | document_type, campus, audience, academic_year, topics, keywords, publication_date | runtime | advanced | Document fields attached to each candidate (title, source and location are always included). |

#### Reranking (`reranking`)

Methods: `cross_encoder` (planned), `llm` (planned), `rule_aware` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `cross_encoder` | `top_n` | integer | 20 | 1.0 … 100.0 (step 1.0) | runtime | basic | Candidates passed to the reranker. |

#### Evidence Selection (`evidence_selection`)

Methods: `top_k` (implemented), `token_budget` (implemented), `diversity` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `top_k` | `max_chunks` | integer | 5 | 1.0 … 20.0 (step 1.0) | runtime | basic | Passages passed to the context builder. |
| `top_k` | `deduplicate` | boolean | true | — | runtime | basic | Drop candidates whose token set overlaps an already selected one. |
| `top_k` | `dedup_similarity` | float | 0.8 | 0.3 … 1.0 (step 0.05) | runtime | advanced | Jaccard similarity of token sets at which a candidate counts as a duplicate. |
| `token_budget` | `max_chunks` | integer | 8 | 1.0 … 20.0 (step 1.0) | runtime | basic | Upper bound on passages. |
| `token_budget` | `max_tokens` | integer | 1200 | 128.0 … 8000.0 (step 64.0) | runtime | basic | Total chunk tokens allowed. |
| `token_budget` | `deduplicate` | boolean | true | — | runtime | basic | Drop near-duplicate candidates. |
| `token_budget` | `dedup_similarity` | float | 0.8 | 0.3 … 1.0 (step 0.05) | runtime | advanced | Jaccard similarity of token sets at which a candidate counts as a duplicate. |

#### Evidence Sufficiency Gate (`sufficiency_gate`)

Methods: `basic` (implemented), `semantic` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `basic` | `min_evidence_chunks` | integer | 1 | 1.0 … 10.0 (step 1.0) | runtime | basic | Abstain when fewer passages are selected. |
| `basic` | `min_dense_score` | float | — | 0.0 … 1.0 (step 0.01) | runtime | basic | Abstain when the best dense similarity is below this value. Empty = off. Uncalibrated — tune with the evaluation set. |

#### Context Builder (`context_builder`)

Methods: `standard` (implemented), `structured` (implemented)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `standard` | `include_source_metadata` | boolean | true | — | runtime | basic | Add title/section/page (and enriched fields) to each source header. |
| `standard` | `max_context_tokens` | integer | 3000 | 256.0 … 16000.0 (step 128.0) | runtime | advanced | Evidence is truncated to fit. Counted with the embedding tokenizer (approximation of the LLM's). |
| `structured` | `include_source_metadata` | boolean | true | — | runtime | basic | Add title/section/page (and enriched fields) to each source. |
| `structured` | `max_context_tokens` | integer | 3000 | 256.0 … 16000.0 (step 128.0) | runtime | advanced | Evidence is truncated to fit. |

#### Generation (`generation`)

Methods: `ollama_chat` (implemented)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `ollama_chat` | `model` | string | — | — | runtime | basic | Installed Ollama model. Empty = OLLAMA_CHAT_MODEL or the first installed model. |
| `ollama_chat` | `temperature` | float | 0.2 | 0.0 … 2.0 (step 0.05) | runtime | basic | Rescales token probabilities: low = focused, high = diverse. Does not add knowledge. |
| `ollama_chat` | `num_predict` | integer | 1024 | -1.0 … 8192.0 (step 32.0) | runtime | basic | Maximum tokens to generate (-1 = unlimited). Thinking models spend part of this on discarded reasoning. |
| `ollama_chat` | `num_ctx` | integer | 4096 | 512.0 … 131072.0 (step 512.0) | runtime | basic | Tokens the model attends to (prompt + answer). Larger uses more memory. |
| `ollama_chat` | `top_p` | float | 0.9 | 0.0 … 1.0 (step 0.05) | runtime | advanced | Nucleus sampling: sample from the smallest set with cumulative probability p. |
| `ollama_chat` | `top_k` | integer | 40 | 1.0 … 200.0 (step 1.0) | runtime | advanced | Sample only from the k most likely tokens. |
| `ollama_chat` | `min_p` | float | 0.0 | 0.0 … 1.0 (step 0.01) | runtime | advanced | Drop tokens with probability below min_p × p(max). |
| `ollama_chat` | `repeat_penalty` | float | 1.1 | 0.5 … 2.0 (step 0.05) | runtime | advanced | Penalize recently generated tokens (>1 = less repetition). |
| `ollama_chat` | `seed` | integer | — | 0.0 … 2147483647.0 (step 1.0) | runtime | advanced | Fixed seed for reproducible sampling. Empty = random. |
| `ollama_chat` | `stop` | string_list | — | — | runtime | advanced | Generation stops when any of these strings is produced. |
| `ollama_chat` | `stream` | boolean | true | — | runtime | basic | Stream answer tokens to the UI as they are generated. |
| `ollama_chat` | `timeout_s` | integer | 120 | 5.0 … 600.0 (step 5.0) | runtime | advanced | Abort generation after this many seconds. |

#### Citation Verification (`citation_verification`)

Methods: `id_span` (implemented), `claim_verification` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `id_span` | `require_citations` | boolean | true | — | runtime | basic | Flag answers that contain no valid citation. |
| `id_span` | `verify_spans` | boolean | true | — | runtime | basic | Re-read the document text at the stored span and compare with the chunk. |

#### Response Guard (`response_guard`)

Methods: `basic` (implemented), `support_based` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `basic` | `on_missing_citations` | enum | warn | warn, abstain | runtime | basic | Policy when no valid citation is present. |
| `basic` | `abstention_message` | string | I could not find enough information i… | — | runtime | advanced | Text returned when the system abstains. |

### Offline stages (ingestion / index)

#### Document Loading (`document_loading`)

Methods: `local_files` (implemented), `hyu_website` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `local_files` | `file_types` | multi_enum | ["pdf", "txt", "md", "html"] | pdf, txt, md, html | ingestion | basic | Extensions to ingest. |
| `local_files` | `recursive` | boolean | true | — | ingestion | basic | Include files in sub-directories. |
| `local_files` | `max_file_mb` | integer | 20 | 1.0 … 200.0 (step 1.0) | ingestion | advanced | Files larger than this are rejected with an error. |

#### Parsing & Normalization (`parsing`)

Methods: `structure_aware` (implemented), `basic` (implemented), `advanced_pdf` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `structure_aware` | `preserve_tables` | boolean | true | — | ingestion | basic | Tables become their own blocks and are never merged with prose by the chunker. |
| `structure_aware` | `normalize_unicode` | boolean | true | — | ingestion | advanced | Normalize characters to NFC before computing spans. |
| `basic` | `normalize_unicode` | boolean | true | — | ingestion | advanced | Normalize characters to NFC before computing spans. |

#### Chunking (`chunking`)

Methods: `structure_aware` (implemented), `fixed` (implemented), `recursive` (planned), `semantic` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `structure_aware` | `chunk_size` | integer | 256 | 32.0 … 512.0 (step 16.0) | ingestion | basic | Target tokens per chunk. |
| `structure_aware` | `chunk_overlap` | integer | 32 | 0.0 … 256.0 (step 8.0) | ingestion | basic | Tokens shared by consecutive windows when a long block is split. |
| `structure_aware` | `min_chunk_size` | integer | 32 | 0.0 … 256.0 (step 8.0) | ingestion | advanced | A section remainder smaller than this is merged into the previous chunk of the same section. |
| `structure_aware` | `max_chunk_size` | integer | 512 | 64.0 … 512.0 (step 16.0) | ingestion | advanced | Hard cap; BGE truncates input beyond 512 tokens. |
| `structure_aware` | `preserve_headings` | boolean | true | — | ingestion | basic | Prepend the section path to the text that is embedded and BM25-indexed (the stored span text is unchanged). |
| `structure_aware` | `tokenizer_id` | string | BAAI/bge-small-en-v1.5 | — | ingestion | advanced | Hugging Face tokenizer used to count tokens. Should match the embedding model. |
| `fixed` | `chunk_size` | integer | 256 | 32.0 … 512.0 (step 16.0) | ingestion | basic | Tokens per window. |
| `fixed` | `chunk_overlap` | integer | 32 | 0.0 … 256.0 (step 8.0) | ingestion | basic | Tokens shared by consecutive windows. |
| `fixed` | `preserve_headings` | boolean | true | — | ingestion | basic | Prepend the section path at the window start to the embedded text. |
| `fixed` | `tokenizer_id` | string | BAAI/bge-small-en-v1.5 | — | ingestion | advanced | Hugging Face tokenizer used to count tokens. |
| `recursive` | `separators` | string_list | ["

", "
", ". ", " "] | — | ingestion | basic | Separator hierarchy, tried in order. |

#### Metadata Extraction (`metadata_extraction`)

Methods: `declared` (implemented), `rule_based` (implemented), `llm` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `declared` | `keywords_per_chunk` | integer | 8 | 0.0 … 20.0 (step 1.0) | ingestion | advanced | Most frequent content terms stored per chunk (0 = none). |
| `rule_based` | `detect_topics` | boolean | true | — | ingestion | basic | Keyword lexicon → topic labels. |
| `rule_based` | `detect_campus` | boolean | true | — | ingestion | basic | Set campus only if exactly one campus is mentioned and none is declared. |
| `rule_based` | `detect_academic_year` | boolean | true | — | ingestion | basic | Regex for 'YYYY academic year' patterns. |
| `rule_based` | `keywords_per_chunk` | integer | 8 | 0.0 … 20.0 (step 1.0) | ingestion | advanced | Most frequent content terms stored per chunk (0 = none). |

#### Embedding (`embedding`)

Methods: `sentence_transformers` (implemented), `ollama_embed` (planned)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `sentence_transformers` | `model_id` | string | BAAI/bge-small-en-v1.5 | — | index | basic | Hugging Face model ID (English BGE small, 384-d). |
| `sentence_transformers` | `model_revision` | string | 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a | — | index | advanced | Pinned commit hash of the model. |
| `sentence_transformers` | `normalize` | boolean | true | — | index | basic | Unit-length vectors make cosine similarity equal to the dot product. |
| `sentence_transformers` | `query_instruction` | string | Represent this sentence for searching… | — | index | advanced | Prefix added to questions (not documents), as recommended for BGE retrieval. |
| `sentence_transformers` | `batch_size` | integer | 32 | 1.0 … 256.0 (step 1.0) | ingestion | advanced | Chunks encoded per forward pass. Affects speed/memory only. |
| `sentence_transformers` | `device` | enum | cpu | cpu, mps, cuda | ingestion | advanced | Compute device for encoding. |

#### Vector Indexing (`vector_indexing`)

Methods: `qdrant` (implemented)

| Method | Parameter | Type | Default | Range / options | Scope | Level | Meaning |
|---|---|---|---|---|---|---|---|
| `qdrant` | `distance` | enum | Cosine | Cosine, Dot, Euclid | index | basic | Similarity function stored in the collection. |
| `qdrant` | `hnsw_m` | integer | 16 | 4.0 … 64.0 (step 1.0) | index | advanced | Graph edges per node. Higher → better recall, more memory. |
| `qdrant` | `hnsw_ef_construct` | integer | 100 | 16.0 … 512.0 (step 4.0) | index | advanced | Candidate list size while building the graph. Higher → better graph, slower build. |

<!-- REGISTRY-TABLE:END -->
