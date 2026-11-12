"""THE METHOD REGISTRY — the single list of every pipeline block, its methods and their settings.

To add a method:  write a subclass of the block's abstract class (app/rag/blocks/<group>/<block>/base.py)
in its own file in that folder, add a `Method(...)` entry to the right `Stage` below, and set
implemented=True once its test passes. The API (GET /api/pipeline/registry) and the UI pick it up.

This file imports the block classes; block files never import this file.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Literal

from app.rag.blocks.pipeline_block import PipelineBlock

# ---- blocks/ingestion/
from app.rag.blocks.ingestion.document_loading.base import BaseDocumentLoader
from app.rag.blocks.ingestion.document_loading.local_loader import LocalFolderLoader
from app.rag.blocks.ingestion.document_loading.web_loader import WebsiteLoader
from app.rag.blocks.ingestion.parsing.base import BaseDocumentParser
from app.rag.blocks.ingestion.parsing.basic_parser import BasicDocumentParser
from app.rag.blocks.ingestion.chunking.base import BaseChunker
from app.rag.blocks.ingestion.chunking.fixed_chunker import FixedTokenChunker
from app.rag.blocks.ingestion.chunking.recursive_chunker import RecursiveChunker
from app.rag.blocks.ingestion.chunking.section_chunker import SectionTokenChunker
from app.rag.blocks.ingestion.chunking.semantic_chunker import SemanticChunker
from app.rag.blocks.ingestion.chunking.whole_document import WholeDocumentChunker
from app.rag.blocks.ingestion.metadata_extraction.applicability_extractor import ApplicabilityExtractor
from app.rag.blocks.ingestion.metadata_extraction.base import BaseMetadataExtractor
from app.rag.blocks.ingestion.metadata_extraction.basic_extractor import BasicMetadataExtractor
from app.rag.blocks.ingestion.metadata_extraction.llm_extractor import LLMMetadataExtractor
from app.rag.blocks.ingestion.embedding.base import BaseEmbedder
from app.rag.blocks.ingestion.embedding.bge_embedder import SentenceTransformerEmbedder
from app.rag.blocks.ingestion.embedding.minilm_embedder import MiniLMEmbedder
from app.rag.blocks.ingestion.embedding.ollama_embedder import OllamaEmbedder
from app.rag.blocks.ingestion.vector_indexing.base import BaseVectorIndexer
from app.rag.blocks.ingestion.vector_indexing.qdrant_indexer import QdrantMongoIndexer

# ---- blocks/query_processing/
from app.rag.blocks.query_processing.query_understanding.base import BaseQueryUnderstanding
from app.rag.blocks.query_processing.query_understanding.llm_understanding import LLMQueryUnderstanding
from app.rag.blocks.query_processing.query_understanding.profile_understanding import ProfileUnderstanding
from app.rag.blocks.query_processing.query_understanding.self_query import SelfQueryUnderstanding
from app.rag.blocks.query_processing.query_understanding.stated_criteria import StatedCriteria
from app.rag.blocks.query_processing.query_rewriting.base import BaseQueryRewriter
from app.rag.blocks.query_processing.query_rewriting.hyde import HyDERewriter
from app.rag.blocks.query_processing.query_rewriting.llm_rewriter import LLMQueryRewriter
from app.rag.blocks.query_processing.query_rewriting.multi_query import MultiQueryRewriter

# ---- blocks/metadata_filtering/
from app.rag.blocks.metadata_filtering.metadata_prefiltering.applicability_prefilter import ApplicabilityPrefilter
from app.rag.blocks.metadata_filtering.metadata_prefiltering.base import BaseMetadataPrefilter
from app.rag.blocks.metadata_filtering.metadata_prefiltering.qdrant_prefilter import QdrantMetadataPrefilter
from app.rag.blocks.metadata_filtering.metadata_postfiltering.base import BaseMetadataPostfilter
from app.rag.blocks.metadata_filtering.metadata_postfiltering.candidate_postfilter import CandidateMetadataPostfilter

# ---- blocks/retrieval/
from app.rag.blocks.retrieval.dense_retrieval.base import BaseDenseRetriever
from app.rag.blocks.retrieval.dense_retrieval.qdrant_cosine import QdrantDenseRetriever
from app.rag.blocks.retrieval.lexical_retrieval.base import BaseLexicalRetriever
from app.rag.blocks.retrieval.lexical_retrieval.bm25 import BM25Retriever
from app.rag.blocks.retrieval.hybrid_fusion.base import BaseHybridFusion
from app.rag.blocks.retrieval.hybrid_fusion.rrf import ReciprocalRankFusion

# ---- blocks/evidence/
from app.rag.blocks.evidence.metadata_enrichment.base import BaseMetadataEnricher
from app.rag.blocks.evidence.metadata_enrichment.mongodb_enrichment import MongoChunkLookup
from app.rag.blocks.evidence.reranking.applicability_reranker import ApplicabilityReranker
from app.rag.blocks.evidence.reranking.base import BaseReranker
from app.rag.blocks.evidence.reranking.coverage_reranker import CoverageReranker
from app.rag.blocks.evidence.reranking.cross_encoder import CrossEncoderReranker
from app.rag.blocks.evidence.reranking.metadata_reranker import MetadataAwareReranker
from app.rag.blocks.evidence.reranking.rankgpt import RankGPTReranker
from app.rag.blocks.evidence.evidence_selection.base import BaseEvidenceSelector
from app.rag.blocks.evidence.evidence_selection.token_budget_selector import TokenBudgetSelector
from app.rag.blocks.evidence.evidence_selection.top_k_selector import TopKSelector
from app.rag.blocks.evidence.evidence_sufficiency.applicability_sufficiency import ApplicabilitySufficiency
from app.rag.blocks.evidence.evidence_sufficiency.base import BaseSufficiencyChecker
from app.rag.blocks.evidence.evidence_sufficiency.sufficiency_checker import ScoreThresholdChecker

# ---- blocks/grounded_generation/
from app.rag.blocks.grounded_generation.context_construction.base import BaseContextBuilder
from app.rag.blocks.grounded_generation.context_construction.standard_context import StandardContextBuilder
from app.rag.blocks.grounded_generation.context_construction.closed_book import ClosedBookBuilder
from app.rag.blocks.grounded_generation.context_construction.conditional_prompt import ConditionalPromptBuilder
from app.rag.blocks.grounded_generation.generation.base import BaseGenerator
from app.rag.blocks.grounded_generation.generation.ollama_generator import OllamaGenerator
from app.rag.schemas import Services

# --------------------------------------------------------------------------- the three building blocks


@dataclass(frozen=True)
class Param:
    """One hyperparameter. `ui` tells the frontend which control to draw.

    scope: "runtime" = used by the next question; "ingestion" = needs re-indexing;
           "index" = changes the stored vectors (needs a fresh index).
    """

    type: Literal["integer", "float", "boolean", "enum", "string"]
    default: Any
    label: str
    description: str
    ui: Literal["slider", "number", "toggle", "select", "text", "ollama_model"] = "slider"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: tuple[str, ...] | None = None
    scope: Literal["runtime", "ingestion", "index"] = "runtime"
    advanced: bool = False  # shown under "Advanced settings" in the UI

    def validate(self, value: Any) -> Any:
        """Return the value with the right Python type, or raise ValueError with a readable message."""
        if self.type == "boolean":
            if not isinstance(value, bool):
                raise ValueError("must be true or false")
            return value
        if self.type in ("integer", "float"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("must be a number")
            if self.type == "integer" and value != int(value):
                raise ValueError("must be a whole number")
            value = int(value) if self.type == "integer" else float(value)
            if self.min is not None and value < self.min:
                raise ValueError(f"must be at least {self.min:g}")
            if self.max is not None and value > self.max:
                raise ValueError(f"must be at most {self.max:g}")
            return value
        if not isinstance(value, str):
            raise ValueError("must be text")
        if self.type == "enum" and value not in (self.options or ()):
            raise ValueError(f"must be one of {', '.join(self.options or ())}")
        return value


@dataclass(frozen=True)
class Method:
    """One algorithm for a block. `cls` must inherit from the block's abstract class."""

    method_id: str
    name: str
    cls: type[PipelineBlock]
    implemented: bool
    description: str
    parameters: dict[str, Param] = field(default_factory=dict)


@dataclass(frozen=True)
class Stage:
    """One pipeline block (= one folder app/rag/blocks/<group>/<stage_id>/). An optional stage can be off (then it is skipped)."""

    stage_id: str  # also the block's folder name
    name: str
    phase: Literal["offline", "online"]
    base_class: type[PipelineBlock]
    description: str
    methods: list[Method]
    default_method: str | None  # None = off by default (optional stages only)
    optional: bool = False

    @property
    def folder(self) -> str:
        """Where the block lives, e.g. "retrieval/dense_retrieval" — taken from its base.py location."""
        return "/".join(self.base_class.__module__.split(".")[3:-1])  # app.rag.blocks.<group>.<block>.base

    @property
    def group(self) -> str:
        """The block's group, shown as a heading in the UI (from the group folder, see GROUPS)."""
        return GROUPS[self.folder.split("/")[0]]


# The group folders in app/rag/blocks/ and the heading the UI shows for each.
GROUPS = {
    "ingestion": "Ingestion",
    "query_processing": "Query Processing",
    "metadata_filtering": "Metadata Filtering",
    "retrieval": "Candidate Retrieval",
    "evidence": "Evidence",
    "grounded_generation": "Grounded Generation",
}


# --------------------------------------------------------------------------- the registry (in pipeline order)

def _chunk_params() -> dict[str, Param]:
    return {
        "chunk_size": Param("integer", 256, "Chunk size (tokens)", "Maximum tokens per chunk. Smaller = more precise matches, less context per chunk.",
                            min=64, max=512, step=16, scope="ingestion"),
        "chunk_overlap": Param("integer", 32, "Chunk overlap (tokens)", "Tokens repeated between neighbouring chunks.",
                               min=0, max=128, step=8, scope="ingestion"),
    }  # fmt: skip


def _llm_params(max_tokens: int, max_tokens_limit: int = 1024) -> dict[str, Param]:
    """Settings of an auxiliary LLM call (rewriting, HyDE, RankGPT). Thinking is always off for these calls."""
    return {
        "model": Param("string", "", "Auxiliary LLM", "Installed Ollama model for this step. Empty = the default model.", ui="ollama_model"),
        "temperature": Param("float", 0.0, "Temperature", "0 = most repeatable output.", min=0, max=1, step=0.05, advanced=True),
        "max_tokens": Param("integer", max_tokens, "Max generated tokens", "Upper limit on the LLM output.", min=16, max=max_tokens_limit,
                            step=16, advanced=True),
    }  # fmt: skip


def _filter_params() -> dict[str, Param]:
    """Shared by prefiltering and postfiltering, so a placement comparison uses the same predicate."""
    return {
        "include_unknown": Param("boolean", True, "Keep documents with unknown values",
                                 "A document that does not state a field (e.g. no campus) stays eligible.", ui="toggle"),
        "include_campus_wide": Param("boolean", True, "Campus-wide documents count",
                                     "A document for ALL campuses is eligible for any campus.", ui="toggle"),
    }  # fmt: skip


def _rerank_depth(default: int) -> Param:
    return Param("integer", default, "Rerank depth", "How many of the top candidates are reordered; the rest keep their order behind them.",
                 ui="number", min=1, max=1000)  # fmt: skip


PIPELINE: list[Stage] = [
    # ======================= OFFLINE: ingestion and indexing =======================
    Stage("document_loading", "Document Loading", "offline", BaseDocumentLoader,
          "Find the files to ingest.", default_method="local_folder", methods=[
              Method("local_folder", "Local folder", LocalFolderLoader, True, "PDF, TXT, Markdown and HTML files in a folder under Sources/data/."),
              Method("website_loader", "HYU website loader", WebsiteLoader, False, "Download approved pages from the HYU website."),
          ]),
    Stage("parsing", "Parsing", "offline", BaseDocumentParser,
          "Read each file into a title and sections (heading, text, page).", default_method="basic_parser", methods=[
              Method("basic_parser", "Basic parser", BasicDocumentParser, True, "Markdown and HTML headings, TXT, PDF pages."),
          ]),
    Stage("chunking", "Chunking", "offline", BaseChunker,
          "Split documents into small pieces that can be searched.", default_method="section_tokens", methods=[
              Method("section_tokens", "Section + token windows", SectionTokenChunker, True,
                     "One chunk per section; long sections become overlapping token windows.", parameters=_chunk_params()),
              Method("fixed_tokens", "Fixed-size token windows", FixedTokenChunker, True,
                     "Windows of N tokens over the whole document, ignoring section boundaries.", parameters=_chunk_params()),
              Method("recursive", "Recursive splitting", RecursiveChunker, True,
                     "Split at paragraphs, then lines, sentences, words; merge up to the token limit.", parameters=_chunk_params()),
              Method("whole_document", "No chunking (whole document)", WholeDocumentChunker, True,
                     "One unit per document (BEIR document-level protocol). Long documents are truncated by the embedder."),
              Method("semantic", "Semantic chunking", SemanticChunker, False, "Cut where the topic changes."),
          ]),
    Stage("metadata_extraction", "Metadata Extraction", "offline", BaseMetadataExtractor,
          "Describe each document (title, language, declared fields).", default_method="basic_metadata", methods=[
              Method("basic_metadata", "Basic metadata", BasicMetadataExtractor, True, "Title, language and fields the file declares itself."),
              Method("applicability_extractor", "Applicability tags (AAES)", ApplicabilityExtractor, True,
                     "Rule-first student applicability tags, with a validated local-LLM fallback.", parameters={
                         "llm_fallback": Param("boolean", True, "LLM fallback", "Ask the auxiliary LLM only when rules find no constraints.",
                                               ui="toggle", scope="ingestion"),
                         "model": Param("string", "qwen3.5:4b", "Auxiliary LLM", "Installed Ollama model used for unmatched chunks.",
                                        ui="ollama_model", scope="ingestion"),
                         "temperature": Param("float", 0.0, "Temperature", "0 = most repeatable output.", min=0, max=1, step=0.05,
                                              scope="ingestion", advanced=True),
                         "max_tokens": Param("integer", 256, "Max generated tokens", "Upper limit on the fallback JSON output.",
                                             min=16, max=1024, step=16, scope="ingestion", advanced=True),
                     }),
              Method("llm_metadata", "LLM metadata extraction", LLMMetadataExtractor, False, "Ask the LLM for campus, audience, deadlines."),
          ]),
    Stage("embedding", "Embedding", "offline", BaseEmbedder,
          "Turn text into vectors. The same method embeds documents and questions.", default_method="bge_small_en", methods=[
              Method("bge_small_en", "BAAI/bge-small-en-v1.5", SentenceTransformerEmbedder, True, "Local Sentence Transformers model, 384 numbers per text."),
              Method("minilm_l6", "all-MiniLM-L6-v2", MiniLMEmbedder, True, "Alternative 384-dimensional model (needs its own index)."),
              Method("ollama_embedding", "Ollama embeddings", OllamaEmbedder, False, "Vectors from an Ollama embedding model."),
          ]),
    Stage("vector_indexing", "Vector Indexing", "offline", BaseVectorIndexer,
          "Store chunks in MongoDB and their vectors in Qdrant.", default_method="qdrant_mongodb", methods=[
              Method("qdrant_mongodb", "Qdrant + MongoDB", QdrantMongoIndexer, True, "Replaces the whole index (cosine distance).", parameters={
                  "hnsw_m": Param("integer", 16, "HNSW m", "Links per vector in the HNSW graph (Qdrant default 16).",
                                  ui="number", min=4, max=64, scope="index", advanced=True),
                  "hnsw_ef_construct": Param("integer", 100, "HNSW ef_construct", "Search breadth while building the graph (Qdrant default 100).",
                                             ui="number", min=16, max=512, scope="index", advanced=True),
                  "indexing_threshold_kb": Param("integer", 20000, "Indexing threshold (KB)",
                                                 "Qdrant builds the HNSW graph only above this size; smaller indexes are full-scanned. 1 = always build.",
                                                 ui="number", min=1, max=1000000, scope="index", advanced=True),
              }),
          ]),
    # ======================= ONLINE: question answering =======================
    Stage("query_understanding", "Query Understanding", "online", BaseQueryUnderstanding,
          "Find what the question asks for, including metadata criteria it states (campus, audience).",
          default_method=None, optional=True, methods=[
              Method("stated_criteria", "Stated criteria (manual)", StatedCriteria, True,
                     "The criteria the student states, set here. No LLM, no guessing.", parameters={
                         field: Param("string", "", label, f"Only {hint} documents (empty = no condition).", ui="text")
                         for field, label, hint in (("campus", "Campus", "this campus's (e.g. SEOUL, ERICA)"),
                                                    ("audience", "Audience", "this audience's (e.g. international)"),
                                                    ("academic_year", "Academic year", "this year's (e.g. 2026)"),
                                                    ("document_type", "Document type", "this type of (e.g. handbook)"))
                     }),
              Method("llm_understanding", "LLM understanding", LLMQueryUnderstanding, False, "The LLM extracts intent and criteria."),
              Method("profile_understanding", "Student profile (AAES step 1)", ProfileUnderstanding, True,
                     "Campus, degree, year, visa, TOPIK … from the question and earlier turns, each stated / remembered / missing."),
              Method("self_query", "Self-query (LLM → profile)", SelfQueryUnderstanding, True,
                     "The LLM writes the student's stated attributes as JSON; values outside the vocabulary are dropped.",
                     parameters=_llm_params(128, 512)),
          ]),
    Stage("query_rewriting", "Query Rewriting", "online", BaseQueryRewriter,
          "Turn the question into a better search query.", default_method=None, optional=True, methods=[
              Method("llm_rewrite", "LLM rewrite", LLMQueryRewriter, True, "The LLM rewrites the question; checked, else the original is used.",
                     parameters=_llm_params(64)),
              Method("multi_query", "Multi-query", MultiQueryRewriter, True, "Several search queries, each searched, merged with RRF.", parameters={
                  **_llm_params(192),
                  "num_queries": Param("integer", 3, "Number of queries", "Extra search queries to generate.", min=2, max=6),
                  "include_original": Param("boolean", True, "Also search the original question", "Keep the question as one of the queries.", ui="toggle"),
                  "rrf_k": Param("integer", 60, "RRF k", "Fusion constant for merging the per-query rankings.", min=1, max=200, advanced=True),
              }),
              Method("hyde", "HyDE", HyDERewriter, True, "Embed an LLM-written hypothetical passage instead of the question.",
                     parameters=_llm_params(160)),
          ]),
    Stage("metadata_prefiltering", "Metadata Prefiltering", "online", BaseMetadataPrefilter,
          "Restrict candidate retrieval to eligible documents: the predicate is applied DURING the search.",
          default_method=None, optional=True, methods=[
              Method("qdrant_prefilter", "Qdrant payload filter", QdrantMetadataPrefilter, True,
                     "Eligibility predicate on Qdrant payload fields (BM25 applies the same predicate).", parameters=_filter_params()),
              Method("applicability_prefilter", "Applicability tags + profile", ApplicabilityPrefilter, True,
                     "Hard filter on the chunk tags with the student's profile and the applicant scope default."),
          ]),
    Stage("dense_retrieval", "Dense Retrieval", "online", BaseDenseRetriever,
          "Find the chunks whose meaning is closest to the question.", default_method="qdrant_cosine", optional=True,
          methods=[
              Method("qdrant_cosine", "Qdrant cosine", QdrantDenseRetriever, True, "Embed the question and find the nearest chunk vectors.", parameters={
                  "top_k": Param("integer", 5, "Top K", "How many of the most similar chunks to retrieve (benchmarks use up to 1000).",
                                 ui="number", min=1, max=1000),
                  "search_mode": Param("enum", "exact", "Search mode", "exact = compare with every vector; hnsw = approximate HNSW graph search.",
                                       ui="select", options=("exact", "hnsw"), advanced=True),
                  "hnsw_ef": Param("integer", 100, "HNSW ef", "Search breadth for hnsw mode: larger = closer to exact, slower.",
                                   ui="number", min=4, max=1024, advanced=True),
              }),
          ]),
    Stage("lexical_retrieval", "Lexical Retrieval", "online", BaseLexicalRetriever,
          "Find chunks that share words with the question.", default_method=None, optional=True,
          methods=[
              Method("bm25", "BM25", BM25Retriever, True, "Classic keyword ranking (Okapi BM25).", parameters={
                  "top_k": Param("integer", 5, "Top K", "How many chunks to retrieve.", ui="number", min=1, max=1000),
                  "k1": Param("float", 1.2, "k1", "How fast repeated words stop adding score (Lucene default 1.2).", min=0, max=3, step=0.1, advanced=True),
                  "b": Param("float", 0.75, "b", "How much long chunks are penalized.", min=0, max=1, step=0.05, advanced=True),
              }),
          ]),
    Stage("hybrid_fusion", "Hybrid Retrieval (Fusion)", "online", BaseHybridFusion,
          "Merge dense and lexical candidates into one list.", default_method=None, optional=True,
          methods=[
              Method("rrf", "Reciprocal Rank Fusion", ReciprocalRankFusion, True, "score = Σ 1/(k + rank).", parameters={
                  "rrf_k": Param("integer", 60, "RRF k", "Larger k = top ranks matter less.", min=1, max=200, advanced=True),
                  "top_k": Param("integer", 5, "Top K", "How many merged chunks to keep.", ui="number", min=1, max=1000),
              }),
          ]),
    Stage("metadata_postfiltering", "Metadata Postfiltering", "online", BaseMetadataPostfilter,
          "Remove ineligible candidates AFTER candidate retrieval (cannot bring back chunks that were not retrieved).",
          default_method=None, optional=True, methods=[
              Method("candidate_postfilter", "Candidate metadata check", CandidateMetadataPostfilter, True,
                     "Check each candidate's document metadata; report removals and starvation.", parameters=_filter_params()),
          ]),
    Stage("metadata_enrichment", "Metadata Enrichment", "online", BaseMetadataEnricher,
          "Load chunk text, section, page and document title from MongoDB.", default_method="mongodb_lookup", methods=[
              Method("mongodb_lookup", "MongoDB lookup", MongoChunkLookup, True, "Look up each candidate by its chunk_id."),
          ]),
    Stage("reranking", "Reranking", "online", BaseReranker,
          "Put the most relevant evidence first.", default_method=None, optional=True, methods=[
              Method("coverage", "Query-term coverage", CoverageReranker, True, "Lesson 5: share of question words found in the chunk.",
                     parameters={"rerank_depth": _rerank_depth(20)}),
              Method("cross_encoder", "Cross-encoder", CrossEncoderReranker, True, "ms-marco-MiniLM-L6-v2 scores question and chunk together.",
                     parameters={
                         "rerank_depth": _rerank_depth(20),
                         "batch_size": Param("integer", 32, "Batch size", "Pairs scored per model call.", ui="number", min=1, max=256, advanced=True),
                         "device": Param("enum", "auto", "Device", "auto = Apple GPU (mps) when available.", ui="select",
                                         options=("auto", "cpu", "mps"), advanced=True),
                     }),
              Method("rankgpt", "RankGPT (LLM listwise)", RankGPTReranker, True, "A local LLM orders the passages; the order is validated.",
                     parameters={
                         **_llm_params(160, 512),
                         "rerank_depth": _rerank_depth(10),
                         "max_words": Param("integer", 80, "Words per passage", "Each passage is cut to this length in the prompt.",
                                            ui="number", min=20, max=300, advanced=True),
                     }),
              Method("metadata_aware", "Metadata-aware", MetadataAwareReranker, False, "Prefer chunks matching the student's situation."),
              Method("applicability_reranker", "Applicability reranker (AAES step 2)", ApplicabilityReranker, True,
                     "Cross-encoder relevance, minus a penalty for evidence that does not apply to the student.", parameters={
                         "rerank_depth": _rerank_depth(20),
                         "batch_size": Param("integer", 32, "Batch size", "Pairs scored per model call.", ui="number", min=1, max=256, advanced=True),
                         "device": Param("enum", "auto", "Device", "auto = Apple GPU (mps) when available.", ui="select",
                                         options=("auto", "cpu", "mps"), advanced=True),
                         "lam": Param("float", 4.0, "λ (conflicting penalty)", "Subtracted from the logit of evidence that conflicts with the profile.",
                                      min=0, max=20, step=0.5),
                         "mu": Param("float", 2.0, "μ (outdated penalty)", "Subtracted from the logit of a superseded version.", min=0, max=20, step=0.5),
                         "hard_filter": Param("boolean", False, "Hard filter (A1)", "Drop conflicting evidence instead of penalizing it.", ui="toggle"),
                     }),
          ]),
    Stage("evidence_selection", "Evidence Selection", "online", BaseEvidenceSelector,
          "Choose which evidence goes into the prompt.", default_method="top_k", methods=[
              Method("top_k", "Top-K (baseline)", TopKSelector, True, "Keep the K best-ranked evidence chunks.", parameters={
                  "top_k": Param("integer", 3, "Top K evidence", "How many of the best-ranked chunks go into the prompt.",
                                 min=1, max=20),
              }),
              Method("token_budget", "Token budget", TokenBudgetSelector, True, "Keep evidence in rank order within a token budget.", parameters={
                  "max_evidence_tokens": Param("integer", 2000, "Evidence token budget", "Maximum total tokens of evidence sent to the LLM.",
                                               min=200, max=8000, step=100),
                  "deduplicate": Param("boolean", False, "Skip duplicate text", "Do not spend budget on a chunk identical to a selected one.",
                                       ui="toggle", advanced=True),
              }),
          ]),
    Stage("evidence_sufficiency", "Evidence Sufficiency", "online", BaseSufficiencyChecker,
          "Decide whether the evidence is good enough to answer; if not, abstain.", default_method=None, optional=True, methods=[
              Method("score_threshold", "Threshold gate", ScoreThresholdChecker, True, "Proceed when the evidence signal reaches a threshold (a heuristic).",
                     parameters={
                         "signal": Param("enum", "query_coverage", "Signal", "query_coverage (Lesson 5) or dense_similarity (best cosine).",
                                         ui="select", options=("query_coverage", "dense_similarity")),
                         "threshold": Param("float", 0.30, "Threshold", "Proceed when the signal is at least this value.", min=0, max=1, step=0.01),
                         "on_missing_signal": Param("enum", "abstain", "If the signal is missing", "abstain or proceed.",
                                                    ui="select", options=("abstain", "proceed"), advanced=True),
                     }),
              Method("applicability_sufficiency", "Applicability sufficiency (AAES steps 3–4)", ApplicabilitySufficiency, True,
                     "Branches + information gain → ANSWER, CONDITIONAL, CLARIFY, ABSTAIN or CONFIRM.", parameters={
                         "relevance_threshold": Param("float", 0.30, "Relevance threshold", "Query coverage a chunk needs to count as relevant.",
                                                      min=0, max=1, step=0.01),
                         "max_branches": Param("integer", 3, "Max branches", "More branches than this → ask one clarifying question.",
                                               ui="number", min=1, max=10),
                         "temporal": Param("boolean", True, "Temporal rule", "Prefer the newest version (off = A6).", ui="toggle"),
                         "policy": Param("enum", "aaes", "Policy", "aaes, always_clarify (A3: ask whenever an attribute is missing), or question_only "
                                         "(A4: ask about what the question mentions, ignoring the evidence).",
                                         ui="select", options=("aaes", "always_clarify", "question_only")),
                     }),
          ]),
    Stage("context_construction", "Context Construction", "online", BaseContextBuilder,
          "Write the evidence into the prompt as [E1], [E2], …", default_method="standard_context", methods=[
              Method("standard_context", "Numbered evidence blocks", StandardContextBuilder, True, "Title, section, page and text for each block."),
              Method("conditional_prompt", "Evidence + 'answer per case or ask'", ConditionalPromptBuilder, True,
                     "The standard blocks plus an instruction to state conditions or ask one question (R16)."),
              Method("closed_book", "No evidence (closed book)", ClosedBookBuilder, True, "The question alone; the model answers from memory (G0)."),
          ]),
    Stage("generation", "Generation", "online", BaseGenerator,
          "Grounded generation: the local LLM answers using only the evidence.", default_method="ollama_chat", methods=[
              Method("ollama_chat", "Ollama chat", OllamaGenerator, True, "Streams the answer from a local Ollama model.", parameters={
                  "model": Param("string", "", "Ollama model", "An installed Ollama model. Empty = the default model.", ui="ollama_model"),
                  "temperature": Param("float", 0.2, "Temperature", "Randomness of the answer. It does not add knowledge.", min=0, max=2, step=0.05),
                  "max_tokens": Param("integer", 1024, "Max generated tokens", "Upper limit on answer length.", min=64, max=4096, step=64),
                  "context_window": Param("integer", 4096, "Context window (tokens)",
                                          "Prompt + answer must fit. Use the same value for every model in a comparison (Llama 2: 4096).",
                                          ui="number", min=1024, max=32768, step=512, advanced=True),
                  "top_p": Param("float", 0.9, "Top P", "Sample only from the most likely tokens covering this probability.", min=0.05, max=1,
                                 step=0.05, advanced=True),
                  "top_k": Param("integer", 40, "Top K tokens", "Sample only from this many most likely tokens.", ui="number", min=1, max=200,
                                 advanced=True),
                  "seed": Param("integer", -1, "Seed", "-1 = random; a fixed seed makes runs more repeatable.", ui="number", min=-1,
                                max=2**31 - 1, advanced=True),
                  "thinking": Param("enum", "off", "Thinking", "off / on (reasoning is never shown) / model_default.", ui="select",
                                    options=("off", "on", "model_default"), advanced=True),
                  "timeout_s": Param("integer", 300, "Timeout (s)", "Give up when the model takes longer.", ui="number", min=10, max=3600,
                                     advanced=True),
              }),
          ]),
]

STAGES: dict[str, Stage] = {s.stage_id: s for s in PIPELINE}


class ConfigError(ValueError):
    """The configuration is invalid. `errors` lists [{stage_id, param, message}]."""

    def __init__(self, errors: list[dict]) -> None:
        super().__init__("; ".join(e["message"] for e in errors))
        self.errors = errors


# --------------------------------------------------------------------------- using the registry


def get_method(stage_id: str, method_id: str) -> Method | None:
    return next((m for m in STAGES[stage_id].methods if m.method_id == method_id), None)


def default_config() -> dict[str, dict]:
    """{stage_id: {"method": id or None, "params": {...defaults}}} for every stage."""
    config = {}
    for stage in PIPELINE:
        method = get_method(stage.stage_id, stage.default_method) if stage.default_method else None
        config[stage.stage_id] = {"method": stage.default_method, "params": {k: p.default for k, p in (method.parameters if method else {}).items()}}
    return config


def validate_config(draft: dict[str, dict] | None) -> dict[str, dict]:
    """Fill in defaults and check everything. Returns the complete config or raises ConfigError.

    `draft` may be partial: {"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 8}}}.
    `"method": None` switches an optional stage off.
    """
    draft = draft or {}
    errors: list[dict] = []
    for stage_id in draft:
        if stage_id not in STAGES:
            errors.append({"stage_id": stage_id, "param": None, "message": f"Unknown stage '{stage_id}'"})
    resolved: dict[str, dict] = {}
    for stage in PIPELINE:
        choice = draft.get(stage.stage_id, {})
        method_id = choice["method"] if "method" in choice else stage.default_method
        if method_id is None:
            if not stage.optional:
                errors.append({"stage_id": stage.stage_id, "param": None, "message": f"{stage.name} needs a method"})
            resolved[stage.stage_id] = {"method": None, "params": {}}
            continue
        method = get_method(stage.stage_id, method_id)
        if method is None:
            errors.append({"stage_id": stage.stage_id, "param": None, "message": f"{stage.name}: unknown method '{method_id}'"})
            continue
        if not method.implemented:
            errors.append({"stage_id": stage.stage_id, "param": None, "message": f"{stage.name}: '{method.name}' is not implemented yet"})
            continue
        given = choice.get("params", {})
        params = {}
        for name in given:
            if name not in method.parameters:
                errors.append({"stage_id": stage.stage_id, "param": name, "message": f"{method.name} has no parameter '{name}'"})
        for name, spec in method.parameters.items():
            try:
                params[name] = spec.validate(given.get(name, spec.default))
            except ValueError as exc:
                errors.append({"stage_id": stage.stage_id, "param": name, "message": f"{spec.label} {exc}"})
        resolved[stage.stage_id] = {"method": method_id, "params": params}
    if not errors:
        errors = _combination_errors(resolved)
    if errors:
        raise ConfigError(errors)
    return resolved


def _combination_errors(config: dict[str, dict]) -> list[dict]:
    """Rules that involve more than one setting or stage."""
    errors = []
    chunking = config["chunking"]["params"]
    if "chunk_overlap" in chunking and chunking["chunk_overlap"] >= chunking["chunk_size"]:
        errors.append({"stage_id": "chunking", "param": "chunk_overlap", "message": "Chunk overlap must be smaller than chunk size"})
    dense, lexical, fusion = (config[s]["method"] for s in ("dense_retrieval", "lexical_retrieval", "hybrid_fusion"))
    if not dense and not lexical:
        errors.append({"stage_id": "dense_retrieval", "param": None, "message": "Choose at least one retriever (dense or lexical)"})
    elif dense and lexical and not fusion:
        errors.append({"stage_id": "hybrid_fusion", "param": None, "message": "Two retrievers are on: choose a Hybrid Fusion method to merge them"})
    elif fusion and not (dense and lexical):
        errors.append({"stage_id": "hybrid_fusion", "param": None, "message": "Hybrid Fusion needs both dense and lexical retrieval"})
    if config["query_rewriting"]["method"] == "hyde" and not dense:
        errors.append({"stage_id": "query_rewriting", "param": None, "message": "HyDE only changes dense retrieval: switch on Dense Retrieval"})
    gate = config["evidence_sufficiency"]
    if gate["method"] and gate["params"].get("signal") == "dense_similarity" and not dense:
        errors.append({"stage_id": "evidence_sufficiency", "param": "signal", "message": "The dense_similarity signal needs Dense Retrieval"})
    for stage_id in ("metadata_prefiltering", "metadata_postfiltering"):
        if config[stage_id]["method"] and not config["query_understanding"]["method"]:
            errors.append({"stage_id": stage_id, "param": None,
                           "message": f"{STAGES[stage_id].name} needs criteria: switch on Query Understanding (e.g. Stated criteria)"})
    return errors


def create_block(stage_id: str, method_id: str, params: dict[str, Any], services: Services) -> PipelineBlock:
    """Create the block object for an IMPLEMENTED method. Planned methods are refused."""
    method = get_method(stage_id, method_id)
    if method is None:
        raise ValueError(f"Unknown method '{method_id}' for stage '{stage_id}'")
    if not method.implemented:
        raise NotImplementedError(f"'{method.name}' ({stage_id}) is registered as not implemented and cannot run")
    block = method.cls(params, services)
    block.method_id = method_id
    return block


def registry_json() -> dict[str, Any]:
    """The registry as JSON for GET /api/pipeline/registry (no Python classes)."""
    stages = []
    for stage in PIPELINE:
        stages.append({
            "stage_id": stage.stage_id,
            "name": stage.name,
            "phase": stage.phase,
            "group": stage.group,
            "description": stage.description,
            "base_class": stage.base_class.__name__,
            "folder": f"app/rag/blocks/{stage.folder}/",
            "optional": stage.optional,
            "default_method": stage.default_method,
            "implemented": any(m.implemented for m in stage.methods),
            "methods": [
                {"method_id": m.method_id, "name": m.name, "description": m.description, "implemented": m.implemented,
                 "class_name": m.cls.__name__, "file": inspect.getfile(m.cls).split("app/rag/blocks/")[-1],
                 "parameters": {name: {"type": p.type, "default": p.default, "label": p.label, "description": p.description,
                                       "ui": p.ui, "min": p.min, "max": p.max, "step": p.step,
                                       "options": list(p.options) if p.options else None, "scope": p.scope, "advanced": p.advanced}
                                for name, p in m.parameters.items()}}
                for m in stage.methods
            ],
        })  # fmt: skip
    return {"stages": stages}


def check_registry() -> None:
    """Catch registry mistakes as soon as the app starts (and in the tests)."""

    def require(ok: bool, message: str) -> None:
        if not ok:
            raise TypeError(f"Registry error: {message}")

    seen_stages, seen_methods = set(), set()
    for stage in PIPELINE:
        require(stage.stage_id not in seen_stages, f"duplicate stage id '{stage.stage_id}'")
        group_folder, _, block_folder = stage.folder.partition("/")
        require(group_folder in GROUPS and block_folder == stage.stage_id,
                f"{stage.base_class.__name__} must live in app/rag/blocks/<group>/{stage.stage_id}/base.py (found {stage.folder})")
        seen_stages.add(stage.stage_id)
        for m in stage.methods:
            require(m.method_id not in seen_methods, f"duplicate method id '{m.method_id}'")
            seen_methods.add(m.method_id)
            require(issubclass(m.cls, stage.base_class), f"{m.cls.__name__} must inherit from {stage.base_class.__name__}")
            require(not inspect.isabstract(m.cls), f"{m.cls.__name__} does not implement every abstract method of {stage.base_class.__name__}")
            for name, p in m.parameters.items():
                try:
                    p.validate(p.default)
                except ValueError as exc:
                    require(False, f"default of '{m.method_id}.{name}' {exc}")
        if stage.default_method is None:
            require(stage.optional, f"required stage '{stage.stage_id}' needs a default method")
        else:
            default = get_method(stage.stage_id, stage.default_method)
            require(default is not None and default.implemented, f"the default method of '{stage.stage_id}' must be an implemented method")


check_registry()
