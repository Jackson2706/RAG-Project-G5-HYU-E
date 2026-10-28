"""THE METHOD REGISTRY — the single list of every pipeline block, its methods and their settings.

To add a method:  write a subclass of the block's abstract class (app/rag/blocks/…),
add a `Method(...)` entry to the right `Stage` below, and set implemented=True once its
test passes. The API (GET /api/pipeline/registry) and the UI pick it up automatically.

This file imports the block classes; block files never import this file.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Literal

from app.rag.blocks.base import PipelineBlock
from app.rag.blocks.chunking import BaseChunker, SectionTokenChunker, SemanticChunker
from app.rag.blocks.embedding import BaseEmbedder, OllamaEmbedder, SentenceTransformerEmbedder
from app.rag.blocks.evidence import BaseEvidenceSelector, BaseSufficiencyGate, ScoreThresholdGate, TokenBudgetSelector
from app.rag.blocks.generation import BaseContextBuilder, BaseGenerator, NumberedContextBuilder, OllamaGenerator
from app.rag.blocks.indexing import BaseVectorIndexer, QdrantMongoIndexer
from app.rag.blocks.loading import BaseDocumentLoader, LocalFolderLoader, WebsiteLoader
from app.rag.blocks.metadata import BaseMetadataExtractor, BasicMetadataExtractor, LLMMetadataExtractor
from app.rag.blocks.parsing import AdvancedPdfParser, BaseDocumentParser, BasicDocumentParser
from app.rag.blocks.query_processing import (BaseConstraintValidator, BaseMetadataFilter, BaseQueryRewriter,
                                             BaseQueryUnderstanding, ExactMetadataFilter, LLMQueryRewriter,
                                             RuleBasedQueryUnderstanding, VocabularyConstraintValidator)  # fmt: skip
from app.rag.blocks.reranking import BaseReranker, CrossEncoderReranker, MetadataAwareReranker
from app.rag.blocks.retrieval import (BaseDenseRetriever, BaseHybridFusion, BaseLexicalRetriever, BaseMetadataEnricher,
                                      BM25Retriever, MongoChunkLookup, QdrantDenseRetriever, ReciprocalRankFusion)  # fmt: skip
from app.rag.blocks.verification import (BaseCitationVerifier, BaseResponseGuard, BasicResponseGuard, ClaimVerifier,
                                         MarkerCitationVerifier)  # fmt: skip
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
    """One pipeline block. An optional stage can be switched off (then the pipeline skips it)."""

    stage_id: str
    name: str
    phase: Literal["offline", "online"]
    base_class: type[PipelineBlock]
    description: str
    methods: list[Method]
    default_method: str | None  # None = off by default (optional stages only)
    optional: bool = False


# --------------------------------------------------------------------------- the registry

PIPELINE: list[Stage] = [
    # ======================= OFFLINE: ingestion (in execution order) =======================
    Stage("document_loading", "Document Loading", "offline", BaseDocumentLoader,
          "Find the files to ingest.", default_method="local_folder", methods=[
              Method("local_folder", "Local folder", LocalFolderLoader, True, "PDF, TXT, Markdown and HTML files in a folder under data/."),
              Method("website_loader", "HYU website loader", WebsiteLoader, False, "Download approved pages from the HYU website."),
          ]),
    Stage("parsing", "Parsing", "offline", BaseDocumentParser,
          "Read each file into a title and sections (heading, text, page).", default_method="basic_parser", methods=[
              Method("basic_parser", "Basic parser", BasicDocumentParser, True, "Markdown and HTML headings, TXT, PDF pages."),
              Method("advanced_pdf", "Advanced PDF parser", AdvancedPdfParser, False, "Layout-aware PDF parsing with tables and OCR."),
          ]),
    Stage("chunking", "Chunking", "offline", BaseChunker,
          "Split documents into small pieces that can be searched.", default_method="section_tokens", methods=[
              Method("section_tokens", "Section + token windows", SectionTokenChunker, True,
                     "One chunk per section; long sections become overlapping token windows.", parameters={
                         "chunk_size": Param("integer", 256, "Chunk size (tokens)", "Maximum tokens per chunk. Smaller = more precise matches, less context per chunk.",
                                             min=64, max=512, step=16, scope="ingestion"),
                         "chunk_overlap": Param("integer", 32, "Chunk overlap (tokens)", "Tokens repeated between neighbouring windows of a long section.",
                                                min=0, max=128, step=8, scope="ingestion"),
                     }),
              Method("semantic", "Semantic chunking", SemanticChunker, False, "Cut where the topic changes."),
          ]),
    Stage("metadata_extraction", "Metadata Extraction", "offline", BaseMetadataExtractor,
          "Describe each document (title, language, declared fields).", default_method="basic_metadata", methods=[
              Method("basic_metadata", "Basic metadata", BasicMetadataExtractor, True, "Title, language and fields the file declares itself."),
              Method("llm_metadata", "LLM metadata extraction", LLMMetadataExtractor, False, "Ask the LLM for campus, audience, deadlines."),
          ]),
    Stage("embedding", "Embedding", "offline", BaseEmbedder,
          "Turn text into vectors. The same method embeds documents and questions.", default_method="bge_small_en", methods=[
              Method("bge_small_en", "BAAI/bge-small-en-v1.5", SentenceTransformerEmbedder, True, "Local Sentence Transformers model, 384 numbers per text."),
              Method("ollama_embedding", "Ollama embeddings", OllamaEmbedder, False, "Vectors from an Ollama embedding model."),
          ]),
    Stage("vector_indexing", "Vector Indexing", "offline", BaseVectorIndexer,
          "Store chunks in MongoDB and their vectors in Qdrant.", default_method="qdrant_mongodb", methods=[
              Method("qdrant_mongodb", "Qdrant + MongoDB", QdrantMongoIndexer, True, "Replaces the whole index (cosine distance)."),
          ]),
    # ======================= ONLINE: answering a question (in execution order) =======================
    Stage("query_understanding", "Query Understanding", "online", BaseQueryUnderstanding,
          "Find constraints in the question (campus, student type).", default_method=None, optional=True, methods=[
              Method("rule_based", "Rule-based", RuleBasedQueryUnderstanding, False, "Keyword rules."),
          ]),
    Stage("query_rewriting", "Query Rewriting", "online", BaseQueryRewriter,
          "Turn the question into a better search query.", default_method=None, optional=True, methods=[
              Method("llm_rewrite", "LLM rewrite", LLMQueryRewriter, False, "The LLM rewrites the question.",
                     parameters={"temperature": Param("float", 0.0, "Temperature", "Randomness of the rewrite.", min=0, max=1, step=0.05)}),
          ]),
    Stage("constraint_validation", "Constraint Validation", "online", BaseConstraintValidator,
          "Keep only valid constraints.", default_method=None, optional=True, methods=[
              Method("vocabulary", "Allowed values", VocabularyConstraintValidator, False, "Values must come from a fixed list."),
          ]),
    Stage("metadata_filtering", "Metadata Filtering", "online", BaseMetadataFilter,
          "Only search documents that apply to the student.", default_method=None, optional=True, methods=[
              Method("exact_filter", "Exact match", ExactMetadataFilter, False, "Metadata must equal the constraint."),
          ]),
    Stage("dense_retrieval", "Dense Retrieval", "online", BaseDenseRetriever,
          "Find the chunks whose meaning is closest to the question.", default_method="qdrant_cosine", optional=True, methods=[
              Method("qdrant_cosine", "Qdrant cosine", QdrantDenseRetriever, True, "Embed the question and find the nearest chunk vectors.", parameters={
                  "top_k": Param("integer", 5, "Top K", "How many of the most similar chunks to retrieve.", min=1, max=20),
              }),
          ]),
    Stage("lexical_retrieval", "Lexical Retrieval", "online", BaseLexicalRetriever,
          "Find chunks that share words with the question.", default_method=None, optional=True, methods=[
              Method("bm25", "BM25", BM25Retriever, False, "Classic keyword ranking.", parameters={
                  "top_k": Param("integer", 5, "Top K", "How many chunks to retrieve.", min=1, max=20),
                  "k1": Param("float", 1.5, "k1", "How fast repeated words stop adding score.", min=0, max=3, step=0.1),
                  "b": Param("float", 0.75, "b", "How much long chunks are penalized.", min=0, max=1, step=0.05),
              }),
          ]),
    Stage("hybrid_fusion", "Hybrid Fusion", "online", BaseHybridFusion,
          "Merge dense and lexical results.", default_method=None, optional=True, methods=[
              Method("rrf", "Reciprocal Rank Fusion", ReciprocalRankFusion, False, "score = Σ 1/(k + rank).", parameters={
                  "rrf_k": Param("integer", 60, "RRF k", "Larger k = top ranks matter less.", min=1, max=200),
                  "top_k": Param("integer", 5, "Top K", "How many merged chunks to keep.", min=1, max=20),
              }),
          ]),
    Stage("metadata_enrichment", "Chunk Lookup", "online", BaseMetadataEnricher,
          "Load chunk text, section, page and document title from MongoDB.", default_method="mongodb_lookup", methods=[
              Method("mongodb_lookup", "MongoDB lookup", MongoChunkLookup, True, "Look up each candidate by its chunk_id."),
          ]),
    Stage("reranking", "Reranking", "online", BaseReranker,
          "Put the most relevant evidence first.", default_method=None, optional=True, methods=[
              Method("cross_encoder", "Cross-encoder", CrossEncoderReranker, False, "Scores question and chunk together.",
                     parameters={"top_n": Param("integer", 5, "Keep top N", "Evidence kept after reranking.", min=1, max=20)}),
              Method("metadata_aware", "Metadata-aware", MetadataAwareReranker, False, "Prefer chunks matching the student's situation."),
          ]),
    Stage("evidence_selection", "Evidence Selection", "online", BaseEvidenceSelector,
          "Choose which evidence goes into the prompt.", default_method="token_budget", methods=[
              Method("token_budget", "Token budget", TokenBudgetSelector, True, "Keep evidence in rank order within a token budget.", parameters={
                  "max_evidence_tokens": Param("integer", 2000, "Evidence token budget", "Maximum total tokens of evidence sent to the LLM.",
                                               min=200, max=8000, step=100),
              }),
          ]),
    Stage("sufficiency_gate", "Evidence Sufficiency", "online", BaseSufficiencyGate,
          "Decide whether the evidence is good enough to answer.", default_method=None, optional=True, methods=[
              Method("score_threshold", "Score threshold", ScoreThresholdGate, False, "Best similarity must reach a minimum.",
                     parameters={"min_score": Param("float", 0.5, "Minimum score", "Lowest acceptable best similarity.", min=0, max=1, step=0.01)}),
          ]),
    Stage("context_builder", "Context Builder", "online", BaseContextBuilder,
          "Write the evidence into the prompt as [E1], [E2], …", default_method="numbered_blocks", methods=[
              Method("numbered_blocks", "Numbered evidence blocks", NumberedContextBuilder, True, "Title, section, page and text for each block."),
          ]),
    Stage("generation", "LLM Generation", "online", BaseGenerator,
          "The local LLM writes an answer using only the evidence.", default_method="ollama_chat", methods=[
              Method("ollama_chat", "Ollama chat", OllamaGenerator, True, "Streams the answer from a local Ollama model.", parameters={
                  "model": Param("string", "", "Ollama model", "An installed Ollama model. Empty = the default model.", ui="ollama_model"),
                  "temperature": Param("float", 0.2, "Temperature", "Randomness of the answer. It does not add knowledge.", min=0, max=2, step=0.05),
                  "max_tokens": Param("integer", 1024, "Max generated tokens", "Upper limit on answer length. Thinking models (qwen3) need about 2048.",
                                      min=64, max=4096, step=64),
              }),
          ]),
    Stage("citation_verification", "Citation Verification", "online", BaseCitationVerifier,
          "Link [E1]-style markers to the real chunks.", default_method="marker_resolution", methods=[
              Method("marker_resolution", "Marker resolution", MarkerCitationVerifier, True, "Every marker must match real evidence; others are removed."),
              Method("claim_verification", "Claim verification", ClaimVerifier, False, "Check each sentence against its cited evidence."),
          ]),
    Stage("response_guard", "Response Guard", "online", BaseResponseGuard,
          "Decide the final answer (or an honest 'not enough information').", default_method="basic_guard", methods=[
              Method("basic_guard", "Basic guard", BasicResponseGuard, True, "Abstain when there is no evidence or the model says so."),
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
            "description": stage.description,
            "base_class": stage.base_class.__name__,
            "optional": stage.optional,
            "default_method": stage.default_method,
            "implemented": any(m.implemented for m in stage.methods),
            "methods": [
                {"method_id": m.method_id, "name": m.name, "description": m.description, "implemented": m.implemented,
                 "class_name": m.cls.__name__,
                 "parameters": {name: {"type": p.type, "default": p.default, "label": p.label, "description": p.description,
                                       "ui": p.ui, "min": p.min, "max": p.max, "step": p.step,
                                       "options": list(p.options) if p.options else None, "scope": p.scope}
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
