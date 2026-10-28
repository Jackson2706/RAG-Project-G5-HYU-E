"""Single source of truth for every pipeline stage, method and hyperparameter.

The frontend renders its Configuration tab from `GET /api/v1/pipeline/registry`;
nothing about available algorithms is hardcoded in the UI. `resolve_config`
turns a partial draft into a complete, frozen snapshot or reports why it can't.

To add a method: append a MethodSpec to the stage below, then implement the
branch in app/rag/stages.py (online) or app/ingestion/ (offline). Leave its
status as ``planned`` until the implementation exists — planned methods are
shown in the UI but rejected by validation.
"""

from __future__ import annotations

from typing import Any

from app.ingestion.loaders import stable_hash
from app.ingestion.metadata import AUDIENCES, CAMPUSES, DOCUMENT_TYPES
from app.models.config import (
    Control,
    ImplementationStatus,
    MethodSpec,
    Option,
    ParameterSpec,
    ParamType,
    PipelineConfig,
    Preset,
    ResolvedConfig,
    ResolvedStageConfig,
    Scope,
    StageConfig,
    StageSpec,
    ValidationIssue,
    ValidationResult,
)

IMPL = ImplementationStatus.implemented
PLANNED = ImplementationStatus.planned

BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
DEFAULT_ABSTENTION = (
    "I could not find enough information in the indexed HYU documents to answer this question. "
    "Please check the official Hanyang University website or contact the relevant office."
)


def _opts(mapping: dict[str, str]) -> list[Option]:
    return [Option(value=k, label=v) for k, v in mapping.items()]


def integer(name, label, default, desc, lo, hi, step=1, **kw) -> ParameterSpec:
    return ParameterSpec(name=name, label=label, type=ParamType.integer, default=default, description=desc,
                         control=kw.pop("control", Control.slider), min=lo, max=hi, step=step, **kw)  # fmt: skip


def number(name, label, default, desc, lo, hi, step, **kw) -> ParameterSpec:
    return ParameterSpec(name=name, label=label, type=ParamType.float, default=default, description=desc,
                         control=kw.pop("control", Control.slider), min=lo, max=hi, step=step, **kw)  # fmt: skip


def boolean(name, label, default, desc, **kw) -> ParameterSpec:
    return ParameterSpec(name=name, label=label, type=ParamType.boolean, default=default, description=desc,
                         control=Control.toggle, **kw)  # fmt: skip


def choice(name, label, default, desc, options: dict[str, str], **kw) -> ParameterSpec:
    return ParameterSpec(name=name, label=label, type=ParamType.enum, default=default, description=desc,
                         control=Control.select, options=_opts(options), **kw)  # fmt: skip


def multi(name, label, default, desc, options: dict[str, str], **kw) -> ParameterSpec:
    return ParameterSpec(name=name, label=label, type=ParamType.multi_enum, default=default, description=desc,
                         control=Control.multiselect, options=_opts(options), **kw)  # fmt: skip


def text(name, label, default, desc, **kw) -> ParameterSpec:
    return ParameterSpec(name=name, label=label, type=ParamType.string, default=default, description=desc,
                         control=kw.pop("control", Control.text), **kw)  # fmt: skip


ING, IDX = Scope.ingestion, Scope.index
ADV = "advanced"

# --------------------------------------------------------------------------- offline stages

OFFLINE_STAGES: list[StageSpec] = [
    StageSpec(
        stage_id="document_loading", stage_name="Document Loading", category="offline",
        description="Discovers source files under the corpus directory and records size, media type and SHA-256.",
        selected_method="local_files", writes=["files"],
        available_methods=[
            MethodSpec(method_id="local_files", display_name="Local files (PDF, TXT, Markdown, HTML)", status=IMPL,
                       implementation="app.ingestion.loaders.discover_files",
                       description="Reads files from data/ in sorted path order. Unsupported or oversized files are reported, never silently skipped.",
                       parameters=[
                           multi("file_types", "File types", ["pdf", "txt", "md", "html"], "Extensions to ingest.",
                                 {"pdf": "PDF", "txt": "Plain text", "md": "Markdown", "html": "HTML"}, scope=ING),
                           boolean("recursive", "Recursive scan", True, "Include files in sub-directories.", scope=ING),
                           integer("max_file_mb", "Max file size", 20, "Files larger than this are rejected with an error.", 1, 200, unit="MB", scope=ING, level=ADV),
                       ]),
            MethodSpec(method_id="hyu_website", display_name="HYU website loader", status=PLANNED,
                       description="Future loader for approved pages of book.hanyang.ac.kr. Must respect access controls; not implemented."),
        ],
    ),
    StageSpec(
        stage_id="parsing", stage_name="Parsing & Normalization", category="offline",
        description="Extracts text, headings, sections, lists, tables and page numbers; normalizes text so every chunk has a recoverable character span.",
        selected_method="structure_aware", dependencies=["document_loading"], reads=["files"], writes=["parsed_documents"],
        available_methods=[
            MethodSpec(method_id="structure_aware", display_name="Structure-aware", status=IMPL,
                       implementation="app.ingestion.parsers.parse_file",
                       description="Keeps heading hierarchy (section paths), tables and PDF pages as separate blocks.",
                       parameters=[
                           boolean("preserve_tables", "Keep tables as blocks", True, "Tables become their own blocks and are never merged with prose by the chunker.", scope=ING),
                           boolean("normalize_unicode", "Unicode NFC normalization", True, "Normalize characters to NFC before computing spans.", scope=ING, level=ADV),
                       ]),
            MethodSpec(method_id="basic", display_name="Basic text", status=IMPL,
                       implementation="app.ingestion.parsers.parse_file",
                       description="Plain paragraphs only; headings are treated as text and no section paths are recorded.",
                       parameters=[
                           boolean("normalize_unicode", "Unicode NFC normalization", True, "Normalize characters to NFC before computing spans.", scope=ING, level=ADV),
                       ]),
            MethodSpec(method_id="advanced_pdf", display_name="Advanced PDF (layout / OCR)", status=PLANNED,
                       description="Layout-aware PDF parsing with table structure and OCR for scanned pages."),
        ],
    ),
    StageSpec(
        stage_id="chunking", stage_name="Chunking", category="offline", requires_reindexing=True,
        description="Splits each document into retrievable chunks measured in real tokenizer tokens, with deterministic chunk IDs.",
        selected_method="structure_aware", dependencies=["parsing"], reads=["parsed_documents"], writes=["chunks"],
        available_methods=[
            MethodSpec(method_id="structure_aware", display_name="Structure-aware", status=IMPL,
                       implementation="app.ingestion.chunking.structure_aware_chunks",
                       description="Packs consecutive blocks of the same section up to the target size; blocks longer than the maximum fall back to overlapping token windows.",
                       parameters=[
                           integer("chunk_size", "Target chunk size", 256, "Target tokens per chunk.", 32, 512, 16, unit="tokens", scope=ING),
                           integer("chunk_overlap", "Window overlap", 32, "Tokens shared by consecutive windows when a long block is split.", 0, 256, 8, unit="tokens", scope=ING),
                           integer("min_chunk_size", "Minimum chunk size", 32, "A section remainder smaller than this is merged into the previous chunk of the same section.", 0, 256, 8, unit="tokens", scope=ING, level=ADV),
                           integer("max_chunk_size", "Maximum chunk size", 512, "Hard cap; BGE truncates input beyond 512 tokens.", 64, 512, 16, unit="tokens", scope=ING, level=ADV),
                           boolean("preserve_headings", "Prefix heading path", True, "Prepend the section path to the text that is embedded and BM25-indexed (the stored span text is unchanged).", scope=ING),
                           text("tokenizer_id", "Tokenizer", "BAAI/bge-small-en-v1.5", "Hugging Face tokenizer used to count tokens. Should match the embedding model.", scope=ING, level=ADV),
                       ]),
            MethodSpec(method_id="fixed", display_name="Fixed token windows", status=IMPL,
                       implementation="app.ingestion.chunking.fixed_chunks",
                       description="Ignores structure; slides a fixed window over the whole document. Useful as an ablation baseline.",
                       parameters=[
                           integer("chunk_size", "Window size", 256, "Tokens per window.", 32, 512, 16, unit="tokens", scope=ING),
                           integer("chunk_overlap", "Window overlap", 32, "Tokens shared by consecutive windows.", 0, 256, 8, unit="tokens", scope=ING),
                           boolean("preserve_headings", "Prefix heading path", True, "Prepend the section path at the window start to the embedded text.", scope=ING),
                           text("tokenizer_id", "Tokenizer", "BAAI/bge-small-en-v1.5", "Hugging Face tokenizer used to count tokens.", scope=ING, level=ADV),
                       ]),
            MethodSpec(method_id="recursive", display_name="Recursive character splitting", status=PLANNED,
                       description="Splits on a separator hierarchy (paragraph → line → sentence → word).",
                       parameters=[ParameterSpec(name="separators", label="Separators", type=ParamType.string_list, default=["\n\n", "\n", ". ", " "],
                                                 description="Separator hierarchy, tried in order.", control=Control.tags, scope=ING)]),
            MethodSpec(method_id="semantic", display_name="Semantic chunking", status=PLANNED,
                       description="Places boundaries where embedding similarity between adjacent sentences drops."),
        ],
    ),
    StageSpec(
        stage_id="metadata_extraction", stage_name="Metadata Extraction", category="offline",
        description="Attaches document metadata (campus, audience, type, dates, topics) and chunk keywords used for filtering and display.",
        selected_method="rule_based", dependencies=["parsing"], reads=["parsed_documents"], writes=["documents.metadata", "chunks.keywords"],
        available_methods=[
            MethodSpec(method_id="declared", display_name="Declared metadata only", status=IMPL,
                       implementation="app.ingestion.metadata.extract_document_metadata",
                       description="Uses only values stated by the source (front matter, HTML meta, PDF info). Unknown values stay unknown.",
                       parameters=[integer("keywords_per_chunk", "Keywords per chunk", 8, "Most frequent content terms stored per chunk (0 = none).", 0, 20, scope=ING, level=ADV)]),
            MethodSpec(method_id="rule_based", display_name="Declared + keyword rules", status=IMPL,
                       implementation="app.ingestion.metadata.extract_document_metadata",
                       description="Adds transparent keyword rules for topics, a single campus mention and academic-year patterns. Inferred fields are marked 'rule' in provenance.",
                       parameters=[
                           boolean("detect_topics", "Detect topics", True, "Keyword lexicon → topic labels.", scope=ING),
                           boolean("detect_campus", "Detect campus", True, "Set campus only if exactly one campus is mentioned and none is declared.", scope=ING),
                           boolean("detect_academic_year", "Detect academic year", True, "Regex for 'YYYY academic year' patterns.", scope=ING),
                           integer("keywords_per_chunk", "Keywords per chunk", 8, "Most frequent content terms stored per chunk (0 = none).", 0, 20, scope=ING, level=ADV),
                       ]),
            MethodSpec(method_id="llm", display_name="LLM semantic extraction", status=PLANNED,
                       description="Future extraction of rules, eligibility conditions, deadlines and exceptions into extracted_facts, each with an evidence span and review status."),
        ],
    ),
    StageSpec(
        stage_id="embedding", stage_name="Embedding", category="offline", requires_reindexing=True,
        description="Encodes chunks (and, at query time, questions) into dense vectors. Defines the embedding contract of an index revision.",
        selected_method="sentence_transformers", dependencies=["chunking"], reads=["chunks"], writes=["vectors"],
        available_methods=[
            MethodSpec(method_id="sentence_transformers", display_name="Sentence Transformers", status=IMPL,
                       implementation="app.services.embeddings.Embedder",
                       description="Local Sentence Transformers model. Vectors from different models/revisions/normalization are never mixed in one collection.",
                       constraints=["Changing model, revision, normalization or query instruction creates a new index revision."],
                       parameters=[
                           text("model_id", "Model", "BAAI/bge-small-en-v1.5", "Hugging Face model ID (English BGE small, 384-d).", scope=IDX),
                           text("model_revision", "Model revision", "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a", "Pinned commit hash of the model.", scope=IDX, level=ADV),
                           boolean("normalize", "L2-normalize vectors", True, "Unit-length vectors make cosine similarity equal to the dot product.", scope=IDX),
                           text("query_instruction", "Query instruction", BGE_QUERY_INSTRUCTION, "Prefix added to questions (not documents), as recommended for BGE retrieval.", scope=IDX, level=ADV, control=Control.textarea),
                           integer("batch_size", "Batch size", 32, "Chunks encoded per forward pass. Affects speed/memory only.", 1, 256, scope=ING, level=ADV),
                           choice("device", "Device", "cpu", "Compute device for encoding.", {"cpu": "CPU", "mps": "Apple GPU (MPS)", "cuda": "NVIDIA GPU (CUDA)"}, scope=ING, level=ADV),
                       ]),
            MethodSpec(method_id="ollama_embed", display_name="Ollama embeddings", status=PLANNED,
                       description="Future provider using Ollama POST /api/embed with an installed embedding model."),
        ],
    ),
    StageSpec(
        stage_id="vector_indexing", stage_name="Vector Indexing", category="offline", requires_reindexing=True,
        description="Writes one Qdrant point per chunk into a new versioned collection, verifies it, then moves the active alias.",
        selected_method="qdrant", dependencies=["embedding"], reads=["vectors", "chunks"], writes=["qdrant_collection"],
        available_methods=[
            MethodSpec(method_id="qdrant", display_name="Qdrant (HNSW + exact search)", status=IMPL,
                       implementation="app.ingestion.pipeline.IngestionPipeline",
                       description="Collection vector size is taken from the embedding model. HNSW graph supports approximate search; exact search is selectable per query.",
                       constraints=["Qdrant local mode (QDRANT_PATH) always performs exact search and ignores HNSW settings."],
                       parameters=[
                           choice("distance", "Distance metric", "Cosine", "Similarity function stored in the collection.", {"Cosine": "Cosine", "Dot": "Dot product", "Euclid": "Euclidean"}, scope=IDX),
                           integer("hnsw_m", "HNSW m", 16, "Graph edges per node. Higher → better recall, more memory.", 4, 64, scope=IDX, level=ADV),
                           integer("hnsw_ef_construct", "HNSW ef_construct", 100, "Candidate list size while building the graph. Higher → better graph, slower build.", 16, 512, 4, scope=IDX, level=ADV),
                       ]),
        ],
    ),
]

# --------------------------------------------------------------------------- online stages

ONLINE_STAGES: list[StageSpec] = [
    StageSpec(
        stage_id="query_understanding", stage_name="Query Understanding", category="online",
        description="Detects language and explicit constraints (campus, audience, academic year) mentioned in the question.",
        selected_method="rule_based", reads=["question"], writes=["understanding"],
        available_methods=[
            MethodSpec(method_id="passthrough", display_name="Pass-through", status=IMPL, implementation="app.rag.stages.QueryUnderstandingStage",
                       description="No analysis; the question is forwarded unchanged."),
            MethodSpec(method_id="rule_based", display_name="Rule-based", status=IMPL, implementation="app.rag.stages.QueryUnderstandingStage",
                       description="Keyword/regex rules over the controlled vocabularies. Detected values are only used if metadata filtering is enabled.",
                       parameters=[
                           boolean("detect_campus", "Detect campus", True, "'Seoul campus' / 'ERICA' mentions."),
                           boolean("detect_audience", "Detect audience", True, "e.g. 'international student', 'graduate'."),
                           boolean("detect_academic_year", "Detect academic year", True, "'2025 academic year' patterns.", level=ADV),
                       ]),
            MethodSpec(method_id="llm", display_name="LLM intent analysis", status=PLANNED, description="Future LLM-based intent and constraint extraction."),
        ],
    ),
    StageSpec(
        stage_id="query_rewriting", stage_name="Query Rewriting", category="online", can_disable=True, enabled=False,
        description="Reformulates the question into one or more retrieval queries. The original question is always preserved.",
        selected_method="llm", reads=["question"], writes=["query", "rewritten_queries"],
        available_methods=[
            MethodSpec(method_id="llm", display_name="LLM rewrite", status=PLANNED, description="Ollama rewrites the question into a self-contained search query.",
                       parameters=[number("temperature", "Temperature", 0.0, "Sampling temperature for the rewrite.", 0, 1, 0.05)]),
            MethodSpec(method_id="multi_query", display_name="Multi-query", status=PLANNED, description="Generates several paraphrases and retrieves for each.",
                       parameters=[integer("num_queries", "Number of queries", 3, "Paraphrases to generate.", 2, 8)]),
        ],
    ),
    StageSpec(
        stage_id="constraint_validation", stage_name="Constraint Validation", category="online",
        description="Validates detected and configured constraints against the controlled vocabularies and resolves conflicts before retrieval.",
        selected_method="deterministic", dependencies=["query_understanding"], reads=["understanding"], writes=["filter_spec"],
        available_methods=[
            MethodSpec(method_id="passthrough", display_name="Pass-through", status=IMPL, implementation="app.rag.stages.ConstraintValidationStage",
                       description="Uses configured filter values only; detected constraints are ignored."),
            MethodSpec(method_id="deterministic", display_name="Deterministic", status=IMPL, implementation="app.rag.stages.ConstraintValidationStage",
                       description="Merges configured and detected constraints; values outside the vocabularies are rejected before retrieval.",
                       parameters=[choice("conflict_policy", "On conflict", "prefer_configured",
                                          "What to do when the question mentions a different campus than the configured filter.",
                                          {"prefer_configured": "Use configured value", "reject": "Stop with a validation error"})]),
        ],
    ),
    StageSpec(
        stage_id="metadata_filtering", stage_name="Metadata Filtering", category="online", can_disable=True, enabled=False,
        description="Restricts retrieval to eligible documents. Compiled to a native Qdrant payload filter (and the same predicate for BM25).",
        selected_method="exact", dependencies=["constraint_validation"], reads=["filter_spec"], writes=["filter_spec"],
        available_methods=[
            MethodSpec(method_id="exact", display_name="Exact match", status=IMPL, implementation="app.rag.retrieval.build_qdrant_filter",
                       description="Field equality on campus, audience, document type, academic year and language.",
                       constraints=["Documents with unknown metadata pass when 'Include unknown' is on — unknown is not the same as ineligible."],
                       parameters=[
                           choice("campus", "Campus", "any", "Restrict to one campus.", {"any": "Any", **{k: v for k, v in CAMPUSES.items() if k != "ALL"}}),
                           multi("audience", "Audience", [], "Keep documents for any of these audiences.", AUDIENCES),
                           choice("document_type", "Document type", "any", "Restrict to one document type.", {"any": "Any", **DOCUMENT_TYPES}, level=ADV),
                           text("academic_year", "Academic year", "", "e.g. 2025 or 2025-2026. Empty = any.", level=ADV),
                           boolean("use_detected_constraints", "Use detected constraints", True, "Apply constraints found by Query Understanding."),
                           boolean("include_unknown", "Include unknown", True, "Keep documents whose field is unknown."),
                           boolean("include_university_wide", "Include university-wide", True, "Keep campus = ALL documents when filtering by campus.", level=ADV),
                       ]),
            MethodSpec(method_id="boolean", display_name="Boolean expressions", status=PLANNED, description="AND/OR/NOT combinations of typed conditions."),
            MethodSpec(method_id="rule_aware", display_name="Rule-aware eligibility", status=PLANNED, description="Uses extracted facts (validity dates, exceptions) to decide eligibility."),
        ],
    ),
    StageSpec(
        stage_id="dense_retrieval", stage_name="Dense Retrieval", category="online", can_disable=True,
        description="Embeds the query with the index's embedding contract and searches Qdrant by vector similarity.",
        selected_method="qdrant_cosine", reads=["query", "filter_spec"], writes=["dense_candidates"],
        available_methods=[
            MethodSpec(method_id="qdrant_cosine", display_name="Qdrant vector search", status=IMPL, implementation="app.rag.retrieval.dense_search",
                       description="Nearest neighbours by the collection's metric (cosine by default).",
                       parameters=[
                           integer("top_k", "Top K", 10, "Candidates returned by vector search.", 1, 100),
                           number("score_threshold", "Score threshold", None, "Discard candidates below this similarity. Empty = none. Uncalibrated.", 0, 1, 0.01, nullable=True, control=Control.number, level=ADV),
                           boolean("exact", "Exact search", False, "Brute-force search instead of the HNSW graph (always exact in local mode).", level=ADV),
                           integer("hnsw_ef", "Search breadth (hnsw_ef)", 128, "HNSW candidate list size at query time. Higher → better recall, slower.", 8, 1024, 8, level=ADV, visible_when={"exact": [False]}),
                       ]),
        ],
    ),
    StageSpec(
        stage_id="lexical_retrieval", stage_name="Lexical Retrieval", category="online", can_disable=True, enabled=False,
        description="Keyword retrieval with Okapi BM25 over the chunks of the active index revision.",
        selected_method="bm25", reads=["query", "filter_spec"], writes=["lexical_candidates"],
        available_methods=[
            MethodSpec(method_id="bm25", display_name="BM25 (Okapi)", status=IMPL, implementation="app.rag.retrieval.BM25Index",
                       description="In-memory BM25 built from MongoDB chunks; rebuilt when the active revision changes.",
                       parameters=[
                           integer("top_k", "Top K", 10, "Candidates returned by BM25.", 1, 100),
                           number("k1", "k1 (term saturation)", 1.5, "How quickly repeated terms stop adding score.", 0, 3, 0.1, level=ADV),
                           number("b", "b (length normalization)", 0.75, "0 = ignore chunk length, 1 = full length normalization.", 0, 1, 0.05, level=ADV),
                           boolean("remove_stopwords", "Remove stopwords", True, "Drop common English function words.", level=ADV),
                       ]),
        ],
    ),
    StageSpec(
        stage_id="hybrid_fusion", stage_name="Hybrid Fusion", category="online",
        description="Merges dense and lexical candidate lists into one ranking.",
        selected_method="none", dependencies=["dense_retrieval", "lexical_retrieval"], reads=["dense_candidates", "lexical_candidates"], writes=["candidates"],
        available_methods=[
            MethodSpec(method_id="none", display_name="No fusion (single retriever)", status=IMPL, implementation="app.rag.retrieval.fuse",
                       description="Forwards the only enabled retriever's list unchanged.", constraints=["Requires exactly one enabled retriever."]),
            MethodSpec(method_id="rrf", display_name="Reciprocal Rank Fusion", status=IMPL, implementation="app.rag.retrieval.fuse",
                       description="score = Σ 1/(k + rank). Uses ranks only, so incomparable score scales don't matter.",
                       parameters=[
                           integer("rrf_k", "RRF constant k", 60, "Larger k flattens the advantage of top ranks.", 1, 200),
                           integer("candidate_limit", "Candidate limit", 20, "Fused candidates kept.", 1, 100),
                       ]),
            MethodSpec(method_id="weighted", display_name="Weighted score fusion", status=IMPL, implementation="app.rag.retrieval.fuse",
                       description="Min-max normalizes each list's scores, then w·dense + (1−w)·lexical.",
                       parameters=[
                           number("dense_weight", "Dense weight", 0.5, "Weight of the dense score; lexical gets 1 − w.", 0, 1, 0.05),
                           integer("candidate_limit", "Candidate limit", 20, "Fused candidates kept.", 1, 100),
                       ]),
        ],
    ),
    StageSpec(
        stage_id="metadata_enrichment", stage_name="Metadata Enrichment", category="online",
        description="Loads chunk text, source location and document metadata from MongoDB for each candidate.",
        selected_method="mongodb_lookup", dependencies=["hybrid_fusion"], reads=["candidates"], writes=["candidates"],
        available_methods=[
            MethodSpec(method_id="mongodb_lookup", display_name="MongoDB lookup", status=IMPL, implementation="app.rag.stages.MetadataEnrichmentStage",
                       description="Batch lookup by chunk_id. Candidates whose chunk is missing are dropped and reported.",
                       parameters=[multi("include_fields", "Included metadata", ["document_type", "campus", "audience", "academic_year", "topics"],
                                         "Document fields attached to each candidate (title, source and location are always included).",
                                         {"document_type": "Document type", "campus": "Campus", "audience": "Audience", "academic_year": "Academic year",
                                          "topics": "Topics", "keywords": "Chunk keywords", "publication_date": "Publication date"}, level=ADV)]),
            MethodSpec(method_id="fact_enrichment", display_name="Fact enrichment", status=PLANNED, description="Attach validated extracted_facts to candidates."),
        ],
    ),
    StageSpec(
        stage_id="reranking", stage_name="Reranking", category="online", can_disable=True, enabled=False,
        description="Re-scores the fused candidates with a more expensive relevance model.",
        selected_method="cross_encoder", dependencies=["metadata_enrichment"], reads=["candidates"], writes=["candidates"],
        available_methods=[
            MethodSpec(method_id="cross_encoder", display_name="Cross-encoder", status=PLANNED, description="Jointly encodes (query, passage) pairs, e.g. a BGE reranker.",
                       parameters=[integer("top_n", "Rerank candidates", 20, "Candidates passed to the reranker.", 1, 100)]),
            MethodSpec(method_id="llm", display_name="LLM reranker", status=PLANNED, description="Ollama scores passage relevance."),
            MethodSpec(method_id="rule_aware", display_name="Rule-aware reranker", status=PLANNED, description="Boosts candidates whose extracted rules apply to the student's constraints."),
        ],
    ),
    StageSpec(
        stage_id="evidence_selection", stage_name="Evidence Selection", category="online",
        description="Chooses the final evidence passages: de-duplicates overlapping chunks and enforces count/token limits.",
        selected_method="top_k", dependencies=["metadata_enrichment"], reads=["candidates"], writes=["evidence"],
        available_methods=[
            MethodSpec(method_id="top_k", display_name="Top K", status=IMPL, implementation="app.rag.stages.EvidenceSelectionStage",
                       description="Keeps the first K distinct candidates in ranked order.",
                       parameters=[
                           integer("max_chunks", "Max evidence chunks", 5, "Passages passed to the context builder.", 1, 20),
                           boolean("deduplicate", "De-duplicate", True, "Drop candidates whose token set overlaps an already selected one."),
                           number("dedup_similarity", "Duplicate threshold", 0.8, "Jaccard similarity of token sets at which a candidate counts as a duplicate.", 0.3, 1, 0.05, level=ADV, visible_when={"deduplicate": [True]}),
                       ]),
            MethodSpec(method_id="token_budget", display_name="Token budget", status=IMPL, implementation="app.rag.stages.EvidenceSelectionStage",
                       description="Like Top K, but also stops when the evidence token budget would be exceeded.",
                       parameters=[
                           integer("max_chunks", "Max evidence chunks", 8, "Upper bound on passages.", 1, 20),
                           integer("max_tokens", "Evidence token budget", 1200, "Total chunk tokens allowed.", 128, 8000, 64, unit="tokens"),
                           boolean("deduplicate", "De-duplicate", True, "Drop near-duplicate candidates."),
                           number("dedup_similarity", "Duplicate threshold", 0.8, "Jaccard similarity of token sets at which a candidate counts as a duplicate.", 0.3, 1, 0.05, level=ADV, visible_when={"deduplicate": [True]}),
                       ]),
            MethodSpec(method_id="diversity", display_name="Diversity-aware (MMR)", status=PLANNED, description="Maximal marginal relevance to balance relevance and source diversity."),
        ],
    ),
    StageSpec(
        stage_id="sufficiency_gate", stage_name="Evidence Sufficiency Gate", category="online",
        description="Decides whether there is usable evidence at all. If not, generation is skipped and the system abstains.",
        selected_method="basic", dependencies=["evidence_selection"], reads=["evidence"], writes=["sufficiency"],
        available_methods=[
            MethodSpec(method_id="basic", display_name="Basic presence check", status=IMPL, implementation="app.rag.stages.SufficiencyGateStage",
                       description="Requires a minimum number of evidence chunks and optionally a minimum dense similarity. A high similarity does not prove the evidence answers the question.",
                       parameters=[
                           integer("min_evidence_chunks", "Minimum evidence chunks", 1, "Abstain when fewer passages are selected.", 1, 10),
                           number("min_dense_score", "Minimum top dense score", None, "Abstain when the best dense similarity is below this value. Empty = off. Uncalibrated — tune with the evaluation set.", 0, 1, 0.01, nullable=True, control=Control.number),
                       ]),
            MethodSpec(method_id="semantic", display_name="Semantic sufficiency", status=PLANNED, description="Model-based judgement of whether the evidence answers the question."),
        ],
    ),
    StageSpec(
        stage_id="context_builder", stage_name="Context Builder", category="online",
        description="Formats the selected evidence with source labels [S1], [S2], … into the prompt.",
        selected_method="standard", dependencies=["sufficiency_gate"], reads=["evidence", "question"], writes=["context_text", "messages", "citations"],
        available_methods=[
            MethodSpec(method_id="standard", display_name="Standard", status=IMPL, implementation="app.rag.generation.build_context",
                       description="Numbered source blocks with a short header (title, section, page).",
                       parameters=[
                           boolean("include_source_metadata", "Include source metadata", True, "Add title/section/page (and enriched fields) to each source header."),
                           integer("max_context_tokens", "Context token budget", 3000, "Evidence is truncated to fit. Counted with the embedding tokenizer (approximation of the LLM's).", 256, 16000, 128, unit="tokens", level=ADV),
                       ]),
            MethodSpec(method_id="structured", display_name="Structured (JSON-like)", status=IMPL, implementation="app.rag.generation.build_context",
                       description="Each source as a key/value block; easier for some models to cite exactly.",
                       parameters=[
                           boolean("include_source_metadata", "Include source metadata", True, "Add title/section/page (and enriched fields) to each source."),
                           integer("max_context_tokens", "Context token budget", 3000, "Evidence is truncated to fit.", 256, 16000, 128, unit="tokens", level=ADV),
                       ]),
        ],
    ),
    StageSpec(
        stage_id="generation", stage_name="Generation", category="online",
        description="Local Ollama chat model writes a grounded answer that cites the source labels.",
        selected_method="ollama_chat", dependencies=["context_builder"], reads=["messages"], writes=["raw_answer"],
        available_methods=[
            MethodSpec(method_id="ollama_chat", display_name="Ollama chat", status=IMPL, implementation="app.services.ollama.OllamaClient.chat_stream",
                       description="Native POST /api/chat. Model options are passed in `options`; reasoning output of thinking models is disabled and never shown.",
                       parameters=[
                           ParameterSpec(name="model", label="Model", type=ParamType.string, default="", control=Control.ollama_model,
                                         description="Installed Ollama model. Empty = OLLAMA_CHAT_MODEL or the first installed model."),
                           number("temperature", "Temperature", 0.2, "Rescales token probabilities: low = focused, high = diverse. Does not add knowledge.", 0, 2, 0.05),
                           integer("num_predict", "Max output tokens", 1024, "Maximum tokens to generate (-1 = unlimited). Thinking models spend part of this on discarded reasoning.", -1, 8192, 32),
                           integer("num_ctx", "Context window", 4096, "Tokens the model attends to (prompt + answer). Larger uses more memory.", 512, 131072, 512, control=Control.number),
                           number("top_p", "Top p", 0.9, "Nucleus sampling: sample from the smallest set with cumulative probability p.", 0, 1, 0.05, level=ADV),
                           integer("top_k", "Top k", 40, "Sample only from the k most likely tokens.", 1, 200, level=ADV),
                           number("min_p", "Min p", 0.0, "Drop tokens with probability below min_p × p(max).", 0, 1, 0.01, level=ADV),
                           number("repeat_penalty", "Repeat penalty", 1.1, "Penalize recently generated tokens (>1 = less repetition).", 0.5, 2, 0.05, level=ADV),
                           integer("seed", "Seed", None, "Fixed seed for reproducible sampling. Empty = random.", 0, 2**31 - 1, nullable=True, control=Control.number, level=ADV),
                           ParameterSpec(name="stop", label="Stop sequences", type=ParamType.string_list, default=[], control=Control.tags, level=ADV,
                                         description="Generation stops when any of these strings is produced."),
                           boolean("stream", "Stream tokens", True, "Stream answer tokens to the UI as they are generated."),
                           integer("timeout_s", "Timeout", 120, "Abort generation after this many seconds.", 5, 600, 5, unit="s", level=ADV),
                       ]),
        ],
    ),
    StageSpec(
        stage_id="citation_verification", stage_name="Citation Verification", category="online",
        description="Checks that every [S#] marker refers to selected evidence and that each cited span resolves to the stored document text.",
        selected_method="id_span", dependencies=["generation"], reads=["raw_answer", "citations"], writes=["citations", "citation_report"],
        available_methods=[
            MethodSpec(method_id="id_span", display_name="ID and span checks", status=IMPL, implementation="app.rag.generation.verify_citations",
                       description="Identity and span resolution only — it does not prove that the cited text supports the claim.",
                       parameters=[
                           boolean("require_citations", "Require citations", True, "Flag answers that contain no valid citation."),
                           boolean("verify_spans", "Verify source spans", True, "Re-read the document text at the stored span and compare with the chunk."),
                       ]),
            MethodSpec(method_id="claim_verification", display_name="Claim verification (NLI)", status=PLANNED, description="Entailment check of each sentence against its cited passage."),
        ],
    ),
    StageSpec(
        stage_id="response_guard", stage_name="Response Guard", category="online",
        description="Final decision: answer, abstain, or answer with a warning, based on the gate and citation checks.",
        selected_method="basic", dependencies=["citation_verification"], reads=["sufficiency", "raw_answer", "citation_report"], writes=["result"],
        available_methods=[
            MethodSpec(method_id="basic", display_name="Basic fallback", status=IMPL, implementation="app.rag.stages.ResponseGuardStage",
                       description="Abstains when the gate failed or the model reported insufficient context; handles missing citations per policy.",
                       parameters=[
                           choice("on_missing_citations", "Missing citations", "warn", "Policy when no valid citation is present.", {"warn": "Answer with a warning", "abstain": "Replace with abstention"}),
                           text("abstention_message", "Abstention message", DEFAULT_ABSTENTION, "Text returned when the system abstains.", control=Control.textarea, level=ADV),
                       ]),
            MethodSpec(method_id="support_based", display_name="Support-based guard", status=PLANNED, description="Removes sentences whose claims are not supported by verified evidence."),
        ],
    ),
]

STAGES: dict[str, StageSpec] = {s.stage_id: s for s in OFFLINE_STAGES + ONLINE_STAGES}
ONLINE_ORDER = [s.stage_id for s in ONLINE_STAGES]
OFFLINE_ORDER = [s.stage_id for s in OFFLINE_STAGES]


def _p(stage: str, method: str | None = None, enabled: bool | None = None, **params: Any) -> dict[str, StageConfig]:
    return {stage: StageConfig(enabled=enabled, method=method, params=params)}


BUILTIN_PRESETS: list[Preset] = [
    Preset(preset_id="baseline_dense", name="Baseline Dense RAG", builtin=True,
           description="Qdrant dense retrieval → MongoDB lookup → Top-K evidence → Ollama. All advanced stages off.",
           config=PipelineConfig(stages={**_p("query_understanding", "passthrough"), **_p("constraint_validation", "passthrough")})),
    Preset(preset_id="hybrid", name="Hybrid Retrieval", builtin=True,
           description="Dense + BM25 fused with Reciprocal Rank Fusion.",
           config=PipelineConfig(stages={**_p("lexical_retrieval", "bm25", True), **_p("hybrid_fusion", "rrf")})),
    Preset(preset_id="metadata_aware", name="Metadata-Aware RAG", builtin=True,
           description="Rule-based constraint detection compiled into a Qdrant payload filter.",
           config=PipelineConfig(stages={**_p("query_understanding", "rule_based"), **_p("constraint_validation", "deterministic"),
                                         **_p("metadata_filtering", "exact", True)})),
    Preset(preset_id="advanced", name="Advanced RAG", builtin=True,
           description="Hybrid + metadata filtering + cross-encoder reranking + token-budget evidence.",
           config=PipelineConfig(stages={**_p("query_understanding", "rule_based"), **_p("metadata_filtering", "exact", True),
                                         **_p("lexical_retrieval", "bm25", True), **_p("hybrid_fusion", "rrf"),
                                         **_p("reranking", "cross_encoder", True), **_p("evidence_selection", "token_budget")})),
]


def default_config() -> PipelineConfig:
    return PipelineConfig(stages={s.stage_id: StageConfig(enabled=s.enabled, method=s.selected_method,
                                                          params={p.name: p.default for p in s.method(s.selected_method).parameters})
                                  for s in STAGES.values()})  # fmt: skip


def resolve_config(draft: PipelineConfig, stage_ids: list[str] | None = None) -> ValidationResult:
    """Validate a partial draft and fill defaults. Only `stage_ids` are resolved (default: all)."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    stage_ids = stage_ids or list(STAGES)
    for unknown in sorted(set(draft.stages) - set(STAGES)):
        errors.append(ValidationIssue(stage_id=unknown, message=f"Unknown stage '{unknown}'"))

    resolved: dict[str, ResolvedStageConfig] = {}
    for stage_id in stage_ids:
        spec = STAGES[stage_id]
        sc = draft.stages.get(stage_id, StageConfig())
        enabled = spec.enabled if sc.enabled is None else sc.enabled
        if not enabled and not spec.can_disable:
            errors.append(ValidationIssue(stage_id=stage_id, message=f"{spec.stage_name} cannot be disabled"))
            enabled = True
        method_id = sc.method or spec.selected_method
        method = spec.method(method_id)
        if method is None:
            errors.append(ValidationIssue(stage_id=stage_id, message=f"Unknown method '{method_id}' for {spec.stage_name}"))
            continue
        if enabled and method.status is not IMPL:
            errors.append(ValidationIssue(stage_id=stage_id, message=f"{spec.stage_name}: '{method.display_name}' is {method.status.value} and cannot be executed"))
        known = {p.name: p for p in method.parameters}
        for name in sorted(set(sc.params) - set(known)):
            # Drafts from the UI may carry values of a previously selected method; ignore them.
            warnings.append(ValidationIssue(stage_id=stage_id, param=name, message=f"Parameter '{name}' does not apply to '{method_id}' and was ignored"))
        params: dict[str, Any] = {}
        for name, p in known.items():
            try:
                params[name] = p.validate_value(sc.params.get(name, p.default))
            except ValueError as exc:
                errors.append(ValidationIssue(stage_id=stage_id, param=name, message=str(exc)))
                params[name] = p.default
        resolved[stage_id] = ResolvedStageConfig(enabled=enabled, method=method_id, params=params)

    errors += _cross_stage_errors(resolved)
    if errors:
        return ValidationResult(valid=False, errors=errors, warnings=warnings)
    snapshot = {k: v.model_dump() for k, v in resolved.items()}
    return ValidationResult(valid=True, warnings=warnings,
                            resolved=ResolvedConfig(stages=resolved, config_hash=stable_hash(snapshot)[:16]))  # fmt: skip


def _cross_stage_errors(r: dict[str, ResolvedStageConfig]) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    if "chunking" in r:
        c = r["chunking"].params
        if c["chunk_overlap"] >= c["chunk_size"]:
            errors.append(ValidationIssue(stage_id="chunking", param="chunk_overlap", message="Overlap must be smaller than chunk size"))
        if "max_chunk_size" in c and not c["min_chunk_size"] <= c["chunk_size"] <= c["max_chunk_size"]:
            errors.append(ValidationIssue(stage_id="chunking", param="chunk_size", message="Require min_chunk_size ≤ chunk_size ≤ max_chunk_size"))
    if "dense_retrieval" in r and "lexical_retrieval" in r:
        retrievers = [s for s in ("dense_retrieval", "lexical_retrieval") if r[s].enabled]
        fusion = r["hybrid_fusion"].method if "hybrid_fusion" in r else "none"
        if not retrievers:
            errors.append(ValidationIssue(stage_id="dense_retrieval", message="Enable at least one retriever (dense or lexical)"))
        elif len(retrievers) == 2 and fusion == "none":
            errors.append(ValidationIssue(stage_id="hybrid_fusion", message="Both retrievers are enabled: choose RRF or weighted fusion"))
        elif len(retrievers) == 1 and fusion != "none":
            errors.append(ValidationIssue(stage_id="hybrid_fusion", message=f"{fusion} fusion needs both dense and lexical retrieval enabled"))
    return errors


def offline_config_differences(resolved: ResolvedConfig, active_offline: dict[str, Any]) -> list[ValidationIssue]:
    """Warn when draft ingestion/index settings differ from the active index revision."""
    issues = []
    for stage_id in OFFLINE_ORDER:
        if stage_id not in resolved.stages or stage_id not in active_offline:
            continue
        if resolved.stages[stage_id].model_dump() != active_offline[stage_id]:
            spec = STAGES[stage_id]
            issues.append(ValidationIssue(stage_id=stage_id, message=f"{spec.stage_name} settings differ from the active index; they take effect only after re-ingestion"))
    return issues


def preset_availability(preset: Preset) -> Preset:
    result = resolve_config(preset.config)
    if result.valid:
        return preset.model_copy(update={"available": True, "unavailable_reason": None})
    return preset.model_copy(update={"available": False, "unavailable_reason": "; ".join(e.message for e in result.errors)})


def registry_payload() -> dict[str, Any]:
    from app.models.pipeline import PipelineContext

    fields = {name: f.description or "" for name, f in PipelineContext.model_fields.items()}
    stages = []
    for s in OFFLINE_STAGES + ONLINE_STAGES:
        d = s.model_dump(mode="json")
        d["implementation_status"] = s.implementation_status.value
        if s.category == "online":
            d["input_schema"] = {k: fields.get(k, "") for k in s.reads}
            d["output_schema"] = {k: fields.get(k, "") for k in s.writes}
        stages.append(d)
    return {"stages": stages, "online_order": ONLINE_ORDER, "offline_order": OFFLINE_ORDER}
