"""Experiment presets: named configurations of registered methods (B0, O0–O8, R0–R14).

A preset only stores method IDs and parameter values; everything else (classes, parameter ranges,
defaults) comes from registry.py, and every preset is checked with validate_config() — the same
check the UI and the API use. Stages a preset does not mention keep their registry defaults, so
each preset changes ONE thing compared with B0 unless it says otherwise (R5, R14 combine methods).

The React Configuration tab offers these presets; the benchmark runner (evaluation/) runs them.
Depths for benchmarks (e.g. 100 documents for Recall@100) are set by the runner, not here: these
values are the ones that make sense for a chat question.
"""

from __future__ import annotations

from typing import Any

from app.rag.registry import ConfigError, validate_config

OFF = {"method": None}
SECTION = {"method": "section_tokens", "params": {"chunk_size": 256, "chunk_overlap": 32}}
HYBRID = {"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 10}}, "lexical_retrieval": {"method": "bm25", "params": {"top_k": 10}},
          "hybrid_fusion": {"method": "rrf", "params": {"rrf_k": 60, "top_k": 20}}}  # fmt: skip
WIDE_DENSE = {"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 20}}}  # rerankers need more than 5 candidates
GATE = {"evidence_sufficiency": {"method": "score_threshold", "params": {"signal": "query_coverage", "threshold": 0.30}}}
CRITERIA = {"query_understanding": {"method": "stated_criteria"}}  # the user fills in campus, audience, …
# AAES: fixed retrieval (hybrid + cross-encoder, Appendix E) with the three AAES steps
AAES = {**HYBRID, "query_understanding": {"method": "profile_understanding"}, "reranking": {"method": "applicability_reranker"},
        "evidence_sufficiency": {"method": "applicability_sufficiency"}}

PRESETS: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- the frozen basic baseline
    {"id": "B0_BASIC_DENSE_RAG", "kind": "baseline", "name": "B0 — Basic Dense RAG",
     "description": "The original app: section chunks 256/32, BGE-small, exact cosine search Top 5, Top-3 evidence, Ollama.",
     "stages": {}},
    # ---------------------------------------------------------------- offline (need their own index)
    {"id": "O0_SECTION_AWARE_256_32", "kind": "offline", "name": "O0 — Section-aware chunking 256/32",
     "description": "The default chunker (same as B0).", "stages": {"chunking": SECTION}},
    {"id": "O1_FIXED_256_32", "kind": "offline", "name": "O1 — Fixed-size token chunking 256/32",
     "description": "Token windows that ignore section boundaries.",
     "stages": {"chunking": {"method": "fixed_tokens", "params": {"chunk_size": 256, "chunk_overlap": 32}}}},
    {"id": "O2_NO_OVERLAP", "kind": "offline", "name": "O2 — No overlap 256/0",
     "description": "Section-aware chunks without overlap.",
     "stages": {"chunking": {"method": "section_tokens", "params": {"chunk_size": 256, "chunk_overlap": 0}}}},
    {"id": "O3_SMALL_CHUNKS", "kind": "offline", "name": "O3 — Small chunks 128/32",
     "description": "Section-aware chunks of 128 tokens, same absolute overlap.",
     "stages": {"chunking": {"method": "section_tokens", "params": {"chunk_size": 128, "chunk_overlap": 32}}}},
    {"id": "O4_LARGE_CHUNKS", "kind": "offline", "name": "O4 — Large chunks 512/32",
     "description": "Section-aware chunks of 512 tokens.",
     "stages": {"chunking": {"method": "section_tokens", "params": {"chunk_size": 512, "chunk_overlap": 32}}}},
    {"id": "O5_RECURSIVE", "kind": "offline", "name": "O5 — Recursive chunking 256/32",
     "description": "Paragraph → line → sentence → word splitting, merged up to 256 tokens.",
     "stages": {"chunking": {"method": "recursive", "params": {"chunk_size": 256, "chunk_overlap": 32}}}},
    {"id": "O6_ALTERNATIVE_EMBEDDING", "kind": "offline", "name": "O6 — all-MiniLM-L6-v2 embeddings",
     "description": "Same chunks as O0, another embedding model (its own index).",
     "stages": {"chunking": SECTION, "embedding": {"method": "minilm_l6"}}},
    {"id": "O7_EXACT_SEARCH", "kind": "offline", "name": "O7 — Exact vector search",
     "description": "Index with a built HNSW graph, searched exactly (the reference for O8).",
     "stages": {"chunking": SECTION, "vector_indexing": {"method": "qdrant_mongodb", "params": {"indexing_threshold_kb": 1}},
                "dense_retrieval": {"method": "qdrant_cosine", "params": {"search_mode": "exact"}}}},
    {"id": "O8_HNSW_ANN", "kind": "offline", "name": "O8 — HNSW approximate search",
     "description": "The same index as O7, searched through the HNSW graph (m 16, ef_construct 100, ef 100).",
     "stages": {"chunking": SECTION, "vector_indexing": {"method": "qdrant_mongodb", "params": {"indexing_threshold_kb": 1}},
                "dense_retrieval": {"method": "qdrant_cosine", "params": {"search_mode": "hnsw", "hnsw_ef": 100}}}},
    {"id": "PROTOCOL_A_WHOLE_DOCUMENT", "kind": "offline", "name": "Protocol A — whole documents",
     "description": "No chunking: one unit per document, for BEIR document-level retrieval.",
     "stages": {"chunking": {"method": "whole_document"}}},
    # ---------------------------------------------------------------- online (use the B0 index)
    {"id": "R0_DENSE", "kind": "online", "name": "R0 — Dense retrieval", "description": "Same as B0.", "stages": {}},
    {"id": "R1_BM25", "kind": "online", "name": "R1 — BM25", "description": "Lexical retrieval only.",
     "stages": {"dense_retrieval": OFF, "lexical_retrieval": {"method": "bm25"}}},
    {"id": "R2_HYBRID_RRF", "kind": "online", "name": "R2 — Hybrid (dense + BM25, RRF)",
     "description": "Both retrievers, merged by Reciprocal Rank Fusion (k = 60).", "stages": HYBRID},
    {"id": "R3_COVERAGE_RERANK", "kind": "online", "name": "R3 — Coverage reranking",
     "description": "Dense Top 20, reordered by query-term coverage (Lesson 5).",
     "stages": {**WIDE_DENSE, "reranking": {"method": "coverage"}}},
    {"id": "R4_CROSS_ENCODER", "kind": "online", "name": "R4 — Cross-encoder reranking",
     "description": "Dense Top 20, reordered by ms-marco-MiniLM-L6-v2.",
     "stages": {**WIDE_DENSE, "reranking": {"method": "cross_encoder"}}},
    {"id": "R5_HYBRID_CROSS_ENCODER", "kind": "online", "name": "R5 — Hybrid + cross-encoder",
     "description": "R2 followed by R4's reranker.", "stages": {**HYBRID, "reranking": {"method": "cross_encoder"}}},
    {"id": "R6_QUERY_REWRITING", "kind": "online", "name": "R6 — LLM query rewriting",
     "description": "One validated rewrite; falls back to the question.", "stages": {"query_rewriting": {"method": "llm_rewrite"}}},
    {"id": "R7_MULTI_QUERY", "kind": "online", "name": "R7 — Multi-query expansion",
     "description": "Question + 3 generated queries, each searched, merged with RRF.", "stages": {"query_rewriting": {"method": "multi_query"}}},
    {"id": "R8_HYDE", "kind": "online", "name": "R8 — HyDE",
     "description": "Dense retrieval with a hypothetical passage's vector.", "stages": {"query_rewriting": {"method": "hyde"}}},
    {"id": "R9_PREFILTERING", "kind": "online", "name": "R9 — Metadata prefiltering",
     "description": "Stated criteria applied inside retrieval (set campus/audience under Query Understanding).",
     "stages": {**CRITERIA, "metadata_prefiltering": {"method": "qdrant_prefilter"}}},
    {"id": "R10_POSTFILTERING", "kind": "online", "name": "R10 — Metadata postfiltering",
     "description": "The same criteria applied after retrieval (may starve).",
     "stages": {**CRITERIA, "metadata_postfiltering": {"method": "candidate_postfilter"}}},
    {"id": "R11_TOKEN_BUDGET_SELECTION", "kind": "online", "name": "R11 — Token-budget evidence selection",
     "description": "Evidence in rank order up to 2000 tokens instead of Top 3.",
     "stages": {"evidence_selection": {"method": "token_budget", "params": {"max_evidence_tokens": 2000}}}},
    {"id": "R12_SUFFICIENCY_GATE", "kind": "online", "name": "R12 — Evidence sufficiency gate",
     "description": "Abstain when the best query coverage is below 0.30 (Lesson 5's heuristic).", "stages": GATE},
    {"id": "R13_RANKGPT", "kind": "online", "name": "R13 — RankGPT listwise reranking",
     "description": "Dense Top 20; a local LLM orders the top 10.", "stages": {**WIDE_DENSE, "reranking": {"method": "rankgpt"}}},
    {"id": "R14_FULL_ADVANCED", "kind": "online", "name": "R14 — Full advanced RAG",
     "description": "Query rewriting → hybrid RRF → cross-encoder → Top-3 → sufficiency gate → generation (no metadata filter).",
     "stages": {"query_rewriting": {"method": "llm_rewrite"}, **HYBRID, "reranking": {"method": "cross_encoder"}, **GATE}},
    # ---------------------------------------------------------------- brackets and new baselines (P6)
    {"id": "G0_CLOSED_BOOK", "kind": "online", "group": "Brackets", "name": "G0 — Closed book",
     "description": "The model answers from memory, with no documents: the lower bracket.",
     "stages": {"context_construction": {"method": "closed_book"}}},
    {"id": "G1_ORACLE_CONTEXT", "kind": "online", "group": "Brackets", "name": "G1 — Oracle context",
     "description": "The model gets the labeled gold evidence: the upper bracket. Runs only in the evaluation runner with a labeled case.",
     "stages": {}, "enabled": False, "disabled_reason": "needs a labeled demo case"},  # P8D enables it
    {"id": "R9S_SCOPE_PREFILTER", "kind": "aaes", "group": "Advanced", "name": "R9-scope — Prefilter on the student's profile",
     "description": "Removes chunks whose tags do not fit what the student said (and applicant-only pages), before the search.",
     "stages": {**HYBRID, "query_understanding": {"method": "profile_understanding"}, "metadata_prefiltering": {"method": "applicability_prefilter"},
                "reranking": {"method": "cross_encoder"}}},
    {"id": "R15_SELF_QUERY", "kind": "aaes", "group": "Advanced", "name": "R15 — Self-query retriever",
     "description": "An LLM turns the question into a metadata filter on the chunk tags (no filter for unstated attributes).",
     "stages": {**HYBRID, "query_understanding": {"method": "self_query"}, "metadata_prefiltering": {"method": "applicability_prefilter"},
                "reranking": {"method": "cross_encoder"}}},
    {"id": "R16_PROMPTED_CONDITIONAL", "kind": "online", "group": "Advanced", "name": "R16 — Prompted conditional answering",
     "description": "R5's retrieval; the prompt tells the model to state conditions per case or ask one question.",
     "stages": {**HYBRID, "reranking": {"method": "cross_encoder"}, "context_construction": {"method": "conditional_prompt"}}},
    # ---------------------------------------------------------------- AAES (need the tagged HYU index)
    {"id": "A0_AAES", "kind": "aaes", "group": "Ours (AAES)", "name": "A0 — AAES full",
     "description": "Reads the student's profile, demotes evidence that does not apply, then answers, answers per case, asks, or refers.",
     "stages": AAES},
    {"id": "A1_AAES_HARD_FILTER", "kind": "aaes", "group": "Ablations", "name": "A1 — AAES with a hard filter",
     "description": "A0, but evidence that does not apply is removed instead of moved down.",
     "stages": {**AAES, "reranking": {"method": "applicability_reranker", "params": {"hard_filter": True}}}},
    {"id": "A3_AAES_ALWAYS_CLARIFY", "kind": "aaes", "group": "Ablations", "name": "A3 — Always clarify",
     "description": "A0, but it asks a question whenever any student detail is missing.",
     "stages": {**AAES, "evidence_sufficiency": {"method": "applicability_sufficiency", "params": {"policy": "always_clarify"}}}},
    {"id": "A6_AAES_NO_TEMPORAL", "kind": "aaes", "group": "Ablations", "name": "A6 — AAES without the temporal rule",
     "description": "A0, but old versions of a notice count as much as the newest one.",
     "stages": {**AAES, "evidence_sufficiency": {"method": "applicability_sufficiency", "params": {"temporal": False}}}},
    # ---------------------------------------------------------------- reserved
    {"id": "PROPOSED_APPROACH", "kind": "proposed", "name": "Proposed approach (not defined yet)",
     "description": "Reserved for the team's own method. Disabled until it is designed and implemented.", "stages": {}, "enabled": False},
]

PRESETS_BY_ID = {p["id"]: p for p in PRESETS}


def preset_config(preset_id: str, overrides: dict[str, dict] | None = None) -> dict[str, dict]:
    """The complete, validated configuration of a preset (plus optional per-stage overrides, e.g. benchmark depths).

    Overrides replace a stage's method and merge its params: {"dense_retrieval": {"params": {"top_k": 100}}}.
    """
    preset = PRESETS_BY_ID[preset_id]
    if not preset.get("enabled", True):
        raise ConfigError([{"stage_id": None, "param": None, "message": f"{preset['name']} is disabled"}])
    stages = {k: {"method": v.get("method"), "params": dict(v.get("params", {}))} for k, v in preset["stages"].items()}
    base = validate_config(stages)
    for stage_id, change in (overrides or {}).items():
        current = base[stage_id]
        method = change.get("method", current["method"])
        params = {**(current["params"] if method == current["method"] else {}), **change.get("params", {})}
        stages[stage_id] = {"method": method, "params": params}
    return validate_config(stages)


def presets_json() -> list[dict[str, Any]]:
    """For GET /api/pipeline/presets: each preset with its validated config (or why it is unavailable)."""
    result = []
    for p in PRESETS:
        entry = {k: p[k] for k in ("id", "kind", "name", "description")} | {"enabled": p.get("enabled", True), "stages": p["stages"],
                                                                           "group": p.get("group")}
        try:
            entry["config"] = preset_config(p["id"]) if entry["enabled"] else None
            entry["errors"] = [] if entry["enabled"] else [{"stage_id": None, "param": None, "message": p.get("disabled_reason", "not available")}]
        except ConfigError as exc:
            entry["config"], entry["errors"] = None, exc.errors
        result.append(entry)
    return result
