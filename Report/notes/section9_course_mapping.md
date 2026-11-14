## 9. Mapping to the course (Lessons 3–6)

Slide numbers refer to the lesson PDFs. "Status" says whether the idea is implemented and measured
(done), implemented but not measured or only measured on BEIR (partial), or deliberately left out (not done).

### Lesson 3 — Ingestion, chunking and vector indexing

| Slide(s) | Course idea | Where it is in HYU Compass | Status |
|---|---|---|---|
| 8–9, 40 | Ingestion contract; the corpus is the source of truth; start from a manifest, not a directory glob | The crawler writes `Sources/data/HYU/manifest.jsonl` (one row per fetched URL) and a frozen snapshot `hyu-20261110-97dc1269`; the snapshot ID contains the first 8 hex digits of the manifest's sha256 | done |
| 10, 41 | Content hashes reveal changed sources; stable document IDs | `source_sha256` of the raw bytes per document; `doc_id = UUIDv5(canonical URL)` (`crawler/extract.py`) | done |
| 11–12, 51 | Parsers preserve provenance; normalization is minimal and versioned | Block-level English filter with `lang_coverage` per document; snapshot spans; VERIFY check `span_text_matches` re-reads the snapshot for every chunk | done |
| 14–17 | Chunking creates retrieval units; `s_tok`, `o_tok`; structure-aware boundaries | Section-aware chunks of 320/48 bge tokens; table rows repeat their header; English-only headers (VERIFY `no_hangul_headers`) | done |
| 18, 27, 50 | Stable chunk IDs; IDs bind content, policy and source span; anti-pattern: IDs that depend on loop order | `chunk_id = UUIDv5(doc_id, chunk index, sha256(text))` (`schemas.py`). The chunking policy is recorded in the index manifest rather than inside the ID | done (policy in manifest, not in ID) |
| 19, 30 | Metadata makes a vector inspectable; a point couples ID, vector and payload | Applicability tags in MongoDB, compact `app_*` filter fields in the Qdrant payload | done |
| 20, 44 | Embedding and index settings form one contract | `BAAI/bge-small-en-v1.5`, 384-d, cosine; VERIFY checks the dimension; the BGE query instruction is set in `config.py`. The model revision and library versions are not written into the index report | partial |
| 21–23, 36–37 | Exact search vs HNSW; HNSW trades exactness for speed | BEIR O7 vs O8 on identical vectors: ANN recall@10 = 1.0, about 6 ms either way, because the collections are small. HYU runs use exact search | partial (BEIR only) |
| 24, 28 | What must trigger re-embedding; incremental rebuild as a decision tree | `DATA.md` §5: r2 and r4/r5 changed tags only and needed 0 new LLM calls; a tag change re-embeds only when tags enter the embedded header | done |
| 25, 31–32 | A checksum at every handoff; build → verify → publish; verification of counts, dimensions, IDs, provenance | `ingest_snapshot.py`: BUILD → VERIFY (15 checks) → PUBLISH; five index revisions r1–r5 kept for rollback; reports in `Report/results/index_reports/` | done |
| 34–35 | DPR; dense gains coexist with a lexical counterexample | BM25 (R1) vs dense (B0) on BEIR, Protocol B nDCG@10: SciFact 0.651 vs 0.716, NFCorpus 0.300 vs 0.346, ArguAna 0.452 vs 0.598 (`Report/results/2026-11-01_main`). Not run on HYU | done (BEIR) |
| 38–39 | Dense X: granularity is an experiment | BEIR chunk-size ablations O0–O5; no proposition-level index | partial |

### Lesson 4 — The RAG mechanism, generation and grounding

| Slide(s) | Course idea | Where it is in HYU Compass | Status |
|---|---|---|---|
| 4–5 | Parametric vs external memory; RAG vs fine-tuning vs long context | G0 closed-book is the parametric-memory-only bracket; no fine-tuning; G1 gives gold evidence only | done |
| 6–7, 28 | Offline indexing vs question-time pipeline | The registry separates offline blocks (loading → indexing) from online blocks (query understanding → generation); one runner for app and evaluator | done |
| 10–11 | Passage size and overlap; provenance and source traceability | See Lesson 3 rows; every answer carries `[E#]` markers resolved to source URLs and spans | done |
| 15 | Lexical, dense and hybrid retrieval | BEIR: R1 BM25, B0 dense, R2 hybrid RRF, R5 hybrid + cross-encoder. HYU: B0 and R5 | done |
| 16 | Query formulation and rewriting | R6 rewrite (with validation and fallback to the original question), R7 multi-query, R8 HyDE (BEIR) | done (BEIR) |
| 17, 19 | Candidate set vs selected evidence; context construction | Candidate Top-K vs evidence Top-3; BEIR failure analysis: a relevant document retrieved but dropped by selection for 13% (SciFact), 14% (NFCorpus) and 35% (ArguAna) of B0 queries | done |
| 18 | Retrieval and reranking | R3 coverage, R4 cross-encoder, R13 RankGPT (BEIR) | done (BEIR) |
| 20 | Context windows and token budgets | R11 token-budget selection (2,000 tokens); `num_ctx` 4,096 recorded for every LLM call | done |
| 22–25 | Claims; supported / contradicted / missing; citation and grounding | Source markers `[E1]…` resolved at runtime; claim-level support is offline evaluation by design (no online citation-verification block) | partial (claim support not scored: no validated judge) |
| 26 | Evidence sufficiency and abstention: "needed facts **and conditions** are available"; clarify an ambiguous request | The definition AAES operationalizes: conditions become applicability tags, and the policy chooses answer / conditional answer / clarify / abstain | done |
| 27 | Failure types and repair priorities | `evaluation/failure_analysis.py` labels the earliest failed stage per query | done |
| 30 | Retrieval quality and response quality are evaluated separately | Applicable-Recall@k and intrusion@k reported apart from action metrics | done |
| 31 | Freshness; conflicting sources need a policy for date, authority and scope; access rules | Version families and `superseded_by`; campus scope (national vs campus); the applicant scope default | done (only 3 superseded documents in the corpus, so the temporal rule never fired: A6 = A0) |
| 33–36 | RAG-Sequence / RAG-Token, Fusion-in-Decoder, FLARE | Not implemented: they need a trained reader or token-level retrieval during decoding, which local Ollama generation does not offer | not done (stated as out of scope) |
| 50 | Controlled comparison: one setting at a time | Each ablation A1–A6 changes one part of A0; BEIR offline ablations change one factor | done |

### Lesson 5 — Improving retrieval and deciding to proceed

| Slide(s) | Course idea | Where it is in HYU Compass | Status |
|---|---|---|---|
| 4 | Information need, relevance, evidence sufficiency | Applicability separates "relevant" from "applies to this student" | done |
| 7–12 | Rewriting, expansion, contextualization; semantic drift; validation and fallback | R6–R8 on BEIR; rewrite drift is a failure category | done (BEIR) |
| 13–16 | Metadata, typed predicates, Boolean logic; filtering by audience and policy year | Typed vocabulary v1 (9 attributes) with alternative condition sets for "TOPIK *or* English track" | done |
| 17–19 | Prefiltering vs postfiltering; candidate starvation; the response policy can clarify, abstain or retry | R9-scope and R15 prefilter; A1 hard filter vs A0 soft penalty; AAES actions follow slide 19's options | done |
| 21–24 | Pointwise, pairwise, listwise ranking; bi- vs cross-encoders | R4/R5 cross-encoder, R13 RankGPT listwise (BEIR) | done (no pairwise method) |
| 25–29 | Ranking vs the decision to proceed; scores vs decision signals; "enough evidence can support No" | AAES steps 2–4; the gold label counts a passage that proves a student is *not* eligible as evidence | done |
| 31–32 | Cost and latency; intervention provenance and rollback | `total_ms` and `llm_calls` per case; index revisions and configs versioned | done |
| 34–37 | Baselines, paired comparisons, ablations, regressions and improvement claims | Pre-registered comparisons with paired bootstrap and Holm correction; per-expected-behaviour and slice tables | done |
| 40–47 | Rewrite–Retrieve–Read, HyDE, RankGPT | R6, R8, R13 | done (BEIR) |

### Lesson 6 — Evaluation, test sets and failure analysis

| Slide(s) | Course idea | Where it is in HYU Compass | Status |
|---|---|---|---|
| 5 | Separate targets: retrieval, answer, attribution, gate | Separate tables for retrieval, actions (gate) and AER; correctness and attribution not scored | partial |
| 6–7 | An inspectable record; case, system and evaluator versions | Run manifests store the label-file sha256 (case version), the git commit, configs and package versions (system version); the evaluator is versioned by its commit, and evaluator v2 records its classifier prompt hash (`summary_v2.md`) | done |
| 8–11 | What belongs in a case; coverage vs representativeness | Five slices sampled on purpose (conditional, temporal, negative, multi-session, unconditional), so averages are diagnostic, not representative | done |
| 12 | Relevance labels need a unit and a rubric | `GUIDELINES.md` v1.3: span-level gold, inapplicable and outdated evidence, expected behaviour | done |
| 14–19 | Recall, precision, reciprocal rank, nDCG | BEIR suite; Applicable-Recall@k on HYU | done |
| 20–22 | Answer quality; citation metrics need a counting unit | Defined in the metric code; not scored on HYU (no human-validated judge) | not done |
| 23–25 | A diagnostic tree locates the earliest defect | Failure categories by earliest stage; the A0 trace analysis in §6–7 | done |
| 26, 28, 30 | Dev vs test; threshold selection on dev; repeated test inspection changes what the test means | One test run (`TEST_RUNS.md`); no tuning of any method; post-hoc fixes evaluated on dev only | done |
| 27 | A gate confusion matrix evaluates a decision | Collapsed 2×2 (proceed vs withhold) plus the 4×4 action matrix | done |
| 31 | An overall improvement can hide a slice regression | Slice tables and per-expected-behaviour tables | done |
| 33 | Small samples limit conclusions | Bootstrap intervals; κ with intervals; the AER comparison had only 2 shared cases | done |
| 34–36 | Deterministic, model-based and human evaluators; a human audit can expose a judge error | Labels were LLM-annotated and LLM-adjudicated with no human audit: stated as the main limitation | not done (limitation) |
| 37–41 | RAGAS dimensions; ARES judge correction | RAGAS-style claim decomposition planned, not scored; ARES-style correction impossible without human labels | not done |
| 42 | RGB: behaviour under controlled contexts | The negative slice (no answer-bearing evidence) and conditional slice play RGB's role for abstention | partial |
| 43 | **The evaluator rule can change a rejection score** | Our own case: evaluator v1 inferred actions from the generation outcome only, so no baseline could ever be scored as giving a conditional answer or asking a question. Evaluator v2 classifies every method's final reply text the same way (§6, evaluator v1 vs v2) | done (finding) |
