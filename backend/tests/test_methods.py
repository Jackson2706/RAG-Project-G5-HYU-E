"""Tests for the baseline methods O1–O8 and R1–R14 (small synthetic inputs, fake models, no Docker/Ollama)."""

import pytest

from app.rag.blocks.evidence.evidence_selection.top_k_selector import TopKSelector
from app.rag.blocks.evidence.evidence_sufficiency.sufficiency_checker import ScoreThresholdChecker
from app.rag.blocks.evidence.reranking.coverage_reranker import CoverageReranker
from app.rag.blocks.evidence.reranking.cross_encoder import CrossEncoderReranker
from app.rag.blocks.evidence.reranking.rankgpt import RankGPTReranker, check_permutation
from app.rag.blocks.ingestion.chunking.fixed_chunker import FixedTokenChunker
from app.rag.blocks.ingestion.chunking.recursive_chunker import RecursiveChunker
from app.rag.blocks.ingestion.chunking.section_chunker import SectionTokenChunker
from app.rag.blocks.ingestion.chunking.whole_document import WholeDocumentChunker
from app.rag.blocks.ingestion.embedding.bge_embedder import SentenceTransformerEmbedder
from app.rag.blocks.ingestion.embedding.minilm_embedder import MiniLMEmbedder
from app.rag.blocks.query_processing.query_rewriting.base import required_terms, validate_rewrite
from app.rag.blocks.query_processing.query_rewriting.hyde import HyDERewriter
from app.rag.blocks.query_processing.query_rewriting.llm_rewriter import LLMQueryRewriter
from app.rag.blocks.query_processing.query_rewriting.multi_query import MultiQueryRewriter
from app.rag.blocks.retrieval.hybrid_fusion.rrf import ReciprocalRankFusion, reciprocal_rank_fusion
from app.rag.blocks.retrieval.lexical_retrieval.bm25 import BM25Retriever, LexicalIndex, bm25_scores, tokenize
from app.rag.pipeline import run_rag
from app.rag.presets import PRESETS, preset_config
from app.rag.registry import validate_config
from app.rag.schemas import Candidate, Evidence, FilterCriteria, ParsedDocument, RetrievalResult, Section
from app.rag.text import query_coverage

pytestmark = pytest.mark.anyio
QUESTION = "What documents do I need for the need-based scholarship?"


def stages_of(trace):
    return {s["stage_id"]: s for s in trace["stages"]}


def evidence(texts: list[str], scores: list[float] | None = None) -> list[Evidence]:
    scores = scores or [1 - i / 10 for i in range(len(texts))]
    return [Evidence(rank=i + 1, chunk_id=f"c{i + 1}", doc_id=f"d{i + 1}", score=s, text=t, title="T", source_uri="x", token_count=len(t.split()),
                     scores={"dense": s}) for i, (t, s) in enumerate(zip(texts, scores))]  # fmt: skip


def embedder(services):
    return SentenceTransformerEmbedder({}, services)


# ------------------------------------------------------------------ offline: chunking (O0–O5, Protocol A)

DOC = ParsedDocument(path="x", source_uri="x", file_type="md", title="T", sections=[
    Section(heading="Intro", text=" ".join(f"intro{i}" for i in range(30))),
    Section(heading="Rules", text="\n\n".join(" ".join(f"p{p}w{i}" for i in range(12)) for p in range(5))),
])  # fmt: skip


@pytest.mark.parametrize("cls", [SectionTokenChunker, FixedTokenChunker, RecursiveChunker, WholeDocumentChunker])
def test_every_chunker_records_valid_source_spans(services, cls):
    services.embedder = embedder(services)
    chunks = cls({"chunk_size": 16, "chunk_overlap": 4}, services).chunk(DOC)
    full = DOC.full_text()
    assert chunks and all(full[c.start : c.end] == c.text for c in chunks)
    if cls is not WholeDocumentChunker:
        assert all(c.token_count <= 16 for c in chunks)


def test_fixed_chunking_is_deterministic_crosses_sections_and_overlaps(services):
    services.embedder = embedder(services)
    chunker = FixedTokenChunker({"chunk_size": 16, "chunk_overlap": 4}, services)
    first, second = chunker.chunk(DOC), chunker.chunk(DOC)
    assert [c.text for c in first] == [c.text for c in second]
    assert any("intro29" in c.text and "p0w0" in c.text for c in first)  # a window spans two sections
    words = [c.text.split() for c in first]
    assert all(a[-4:] == b[:4] for a, b in zip(words, words[1:]))  # exactly 4 tokens of overlap (1 word = 1 fake token)


def test_section_chunking_never_crosses_sections_and_no_overlap_option(services):
    services.embedder = embedder(services)
    chunks = SectionTokenChunker({"chunk_size": 16, "chunk_overlap": 0}, services).chunk(DOC)
    assert not any("intro29" in c.text and "p0w0" in c.text for c in chunks)
    intro = [c.text.split() for c in chunks if c.section == "Intro"]
    assert sum(len(w) for w in intro) == 30  # O2: no overlap → no repeated tokens


def test_recursive_chunking_splits_at_paragraphs_first(services):
    services.embedder = embedder(services)
    chunks = [c for c in RecursiveChunker({"chunk_size": 30, "chunk_overlap": 0}, services).chunk(DOC) if c.section == "Rules"]
    assert all(not c.text.startswith(("w", " ")) and c.text.split()[0].endswith("w0") for c in chunks)  # every chunk starts at a paragraph


def test_whole_document_is_one_unit(services):
    services.embedder = embedder(services)
    (chunk,) = WholeDocumentChunker({}, services).chunk(DOC)
    assert chunk.text == DOC.full_text() and chunk.section is None


def test_embedding_contract_and_dimensions(services):
    bge, minilm = embedder(services), MiniLMEmbedder({}, services)
    assert len(bge.embed_query("hi")) == bge.dimension() == 64  # the fake model
    c1, c2 = bge.contract(), minilm.contract()
    assert c1["model"] == "BAAI/bge-small-en-v1.5" and c1["query_prefix"].startswith("Represent")
    assert c2["model"] == "sentence-transformers/all-MiniLM-L6-v2" and c2["query_prefix"] == "" and c2["revision"]


# ------------------------------------------------------------------ offline: index manifest, exact vs HNSW (O7, O8)


async def test_index_manifest_records_contract_spans_and_hnsw_status(ingested, db):
    m = db.get_manifest()
    assert m["chunks"] == db.chunks.count_documents({}) == db.qdrant.count(db.collection).count  # MongoDB and Qdrant agree
    assert m["source_spans_invalid"] == 0 and m["embedding_contract"]["dimension"] == 64
    assert m["config"]["chunking"]["method"] == "section_tokens" and "hnsw_built" in m["vector_index"]
    assert set(m["timings"]) >= {"chunk_ms", "embed_ms", "index_ms", "total_ms"}
    first = db.chunks.find_one({}, {"_id": 0})
    point = db.qdrant.retrieve(db.collection, [first["chunk_id"]], with_payload=True)[0]
    assert point.payload["doc_id"] == first["doc_id"]


async def test_hnsw_search_is_refused_without_a_built_graph(ingested, services):
    config = validate_config({"dense_retrieval": {"method": "qdrant_cosine", "params": {"search_mode": "hnsw"}}})
    trace = await run_rag(QUESTION, config, services)
    assert trace["status"] == "failed" and "no HNSW graph" in trace["error"]  # never report a full scan as HNSW
    exact = await run_rag(QUESTION, validate_config({}), services)
    assert stages_of(exact)["dense_retrieval"]["output"]["details"]["search_mode"] == "exact"


async def test_reingesting_is_reproducible(ingested, corpus, db, services):
    before = db.get_manifest()["chunk_id_sha256"]
    from app.rag.pipeline import run_ingestion

    run_ingestion(corpus, validate_config({}), services)
    assert db.get_manifest()["chunk_id_sha256"] == before


# ------------------------------------------------------------------ R1 BM25 and R2 RRF


def test_bm25_scores_and_ordering():
    assert tokenize("The Add/Drop period?") == ["add", "drop", "period"]
    index = LexicalIndex(["a", "b", "c"], ["d", "d", "d"], [{}, {}, {}], __import__("numpy").array([3.0, 3.0, 6.0]), {}, 0.0)
    import numpy as np

    index.postings = {"credit": (np.array([0, 2]), np.array([2.0, 1.0])), "limit": (np.array([1]), np.array([1.0]))}
    scores = bm25_scores(index, ["credit", "limit"], k1=1.2, b=0.75)
    assert scores[1] > scores[0] > scores[2] > 0  # rare word "limit" beats a common one; the long chunk is penalized
    assert bm25_scores(index, ["unknown"], 1.2, 0.75).sum() == 0


async def test_bm25_retriever_returns_real_bm25_scores(ingested, services):
    result = await BM25Retriever({"top_k": 3, "k1": 1.2, "b": 0.75}, services).retrieve("household income certificate scholarship")
    scores = [c.score for c in result.candidates]
    assert scores == sorted(scores, reverse=True) and scores[0] > 1 and result.candidates[0].scores == {"bm25": scores[0]}
    assert "not a cosine" in result.details["score"]


def test_rrf_ranks_deduplicates_and_records_origins():
    a = [Candidate(rank=1, chunk_id="x", doc_id="d", score=0.9, scores={"dense": 0.9}), Candidate(rank=2, chunk_id="y", doc_id="d", score=0.8)]
    b = [Candidate(rank=1, chunk_id="y", doc_id="d", score=12.0, scores={"bm25": 12.0}), Candidate(rank=2, chunk_id="z", doc_id="d", score=5.0)]
    fused = reciprocal_rank_fusion({"dense": a, "lexical": b}, k=60, top_k=10)
    assert [c.chunk_id for c in fused] == ["y", "x", "z"]  # y is in both lists
    assert fused[0].score == pytest.approx(1 / 62 + 1 / 61, abs=1e-6) and fused[0].scores["dense_rank"] == 2 and fused[0].scores["lexical_rank"] == 1
    assert [c.rank for c in fused] == [1, 2, 3]


async def test_rrf_block_and_hybrid_pipeline(ingested, services):
    trace = await run_rag(QUESTION, preset_config("R2_HYBRID_RRF"), services)
    s = stages_of(trace)
    assert all(s[x]["status"] == "completed" for x in ("dense_retrieval", "lexical_retrieval", "hybrid_fusion"))
    assert sum(s["hybrid_fusion"]["output"]["details"]["found_by"].values()) == len(s["hybrid_fusion"]["output"]["candidates"])
    result = await ReciprocalRankFusion({"rrf_k": 60, "top_k": 1}, services).fuse(RetrievalResult(candidates=[]), RetrievalResult(candidates=[]))
    assert result.candidates == []


# ------------------------------------------------------------------ R3 coverage, R4 cross-encoder, R13 RankGPT


async def test_coverage_reranking_follows_lesson5(services):
    items = evidence(["campus map", "scholarship documents needed: income certificate", "scholarship deadline"], [0.9, 0.5, 0.8])
    out = await CoverageReranker({"rerank_depth": 20}, services).rerank(QUESTION, items)
    assert [e.chunk_id for e in out] == ["c2", "c3", "c1"] and out[0].scores["rank_before"] == 2
    assert out[0].scores["coverage"] == pytest.approx(query_coverage(QUESTION, items[1].text))
    tie = await CoverageReranker({"rerank_depth": 20}, services).rerank("zzz", evidence(["a", "b"], [0.1, 0.9]))
    assert [e.chunk_id for e in tie] == ["c2", "c1"]  # equal coverage: higher incoming score first


async def test_cross_encoder_keeps_identity_and_tail(services, monkeypatch):
    class FakeCrossEncoder:
        def predict(self, pairs, **kw):
            return [float(len(set(q.lower().split()) & set(t.lower().split()))) for q, t in pairs]

    monkeypatch.setattr("app.rag.blocks.evidence.reranking.cross_encoder.load_cross_encoder", lambda device: FakeCrossEncoder())
    items = evidence(["unrelated", "need based scholarship documents", "tail item"])
    out = await CrossEncoderReranker({"rerank_depth": 2, "batch_size": 8, "device": "cpu"}, services).rerank("need based scholarship", items)
    assert [e.chunk_id for e in out] == ["c2", "c1", "c3"] and {e.chunk_id for e in out} == {e.chunk_id for e in items}
    assert out[0].scores["cross_encoder"] == 3.0 and "cross_encoder" not in out[2].scores  # the tail was not scored


def test_rankgpt_permutation_validation():
    assert check_permutation("[2] > [1] > [3]", 3) == {"order": [2, 1, 3], "invalid": [], "duplicates": [], "missing": []}
    bad = check_permutation("[2] > [2] > [9] > [1]", 3)
    assert bad == {"order": [2, 1], "invalid": [9], "duplicates": [2], "missing": [3]}


async def test_rankgpt_repairs_or_falls_back(services, fake_ollama):
    items = evidence(["a", "b", "c", "d"])
    fake_ollama.answer = "[3] > [1] > [3]"  # duplicate + 2 missing, but half ranked → repaired after a retry
    out = await (block := RankGPTReranker({"model": "", "temperature": 0.0, "max_tokens": 64, "rerank_depth": 4, "max_words": 20}, services)).rerank("q", items)
    assert [e.chunk_id for e in out] == ["c3", "c1", "c2", "c4"] and block.trace_details["outcome"] == "repaired"
    assert len(block.trace_details["attempts"]) == 2 and out[0].score == items[2].score  # no invented relevance score
    fake_ollama.answer = "I cannot rank these."
    out = await block.rerank("q", items)
    assert [e.chunk_id for e in out] == ["c1", "c2", "c3", "c4"] and block.trace_details["outcome"] == "fallback_original_order"


# ------------------------------------------------------------------ R6 rewriting, R7 multi-query, R8 HyDE


def test_rewrite_validation_keeps_constraints():
    q = 'Can ERICA students without a visa apply before March 2026 for the "need-based" scholarship?'
    assert {"ERICA", "2026", "need-based", "March"} <= set(required_terms(q))
    assert validate_rewrite(q, 'ERICA "need-based" scholarship March 2026 students without visa')["passed"]
    dropped = validate_rewrite(q, "need-based scholarship application")
    assert not dropped["passed"] and "2026" in dropped["missing"]
    assert not validate_rewrite("Which courses do not need a prerequisite?", "courses prerequisite")["passed"]  # negation lost
    assert not validate_rewrite("credits", "")["passed"]


async def test_llm_rewrite_used_or_falls_back(ingested, services, fake_ollama):
    params = {"model": "", "temperature": 0.0, "max_tokens": 64}
    fake_ollama.answer = "need-based scholarship required documents"
    good = await LLMQueryRewriter(params, services).rewrite(QUESTION)
    assert good.query == "need-based scholarship required documents" and good.validation["used"] == "rewrite"
    question = "How many credits can I take in 2026?"
    fake_ollama.answer = "credit limit"  # drops 2026
    bad = await LLMQueryRewriter(params, services).rewrite(question)
    assert bad.query == question and bad.validation["used"] == "original question" and "2026" in bad.validation["missing"]


async def test_multi_query_generates_searches_each_and_merges(ingested, services, fake_ollama):
    fake_ollama.answer = "1. need-based scholarship documents\n2. income certificate scholarship\n2. income certificate scholarship\n- tuition waiver"
    rewritten = await MultiQueryRewriter({"model": "", "temperature": 0.0, "max_tokens": 64, "num_queries": 3, "include_original": True,
                                          "rrf_k": 60}, services).rewrite(QUESTION)  # fmt: skip
    assert rewritten.query == QUESTION and rewritten.alternatives == ["need-based scholarship documents", "income certificate scholarship",
                                                                      "tuition waiver"]  # numbering removed, duplicate dropped  # fmt: skip
    trace = await run_rag(QUESTION, preset_config("R7_MULTI_QUERY"), services)
    dense = stages_of(trace)["dense_retrieval"]
    assert len(dense["input"]["queries"]) == 4 and len(dense["output"]["details"]["per_query"]) == 4
    ids = [c["chunk_id"] for c in dense["output"]["candidates"]]
    assert len(ids) == len(set(ids)) and "query_1_rank" in str(dense["output"]["candidates"])


async def test_hyde_passage_is_only_a_search_vector(ingested, services, fake_ollama):
    fake_ollama.answer = "Applicants submit a household income certificate and an application form to the scholarship office."
    hyde = await HyDERewriter({"model": "", "temperature": 0.0, "max_tokens": 64}, services).rewrite(QUESTION)
    assert hyde.query == QUESTION and hyde.embedding_text.startswith("Applicants")
    fake_ollama.answer = "The answer is in the evidence [E1]."
    trace = await run_rag(QUESTION, preset_config("R8_HYDE"), services)
    s = stages_of(trace)
    assert s["dense_retrieval"]["output"]["details"]["embedded"] == "hypothetical passage (HyDE)"
    passage = s["query_rewriting"]["output"]["embedding_text"]
    assert all(passage not in e["text"] for e in s["evidence_selection"]["output"])  # never evidence
    assert all(passage not in src["excerpt"] for src in trace["sources"])  # never a source
    assert s["context_construction"]["input"]["question"] == QUESTION


# ------------------------------------------------------------------ R9/R10 (predicate), R11 selection, R12 gate


def test_same_predicate_for_both_filter_placements():
    p = FilterCriteria(campus="ERICA").to_filter()
    assert p.conditions == {"campus": ["erica", "all"]} and p.include_unknown
    assert p.matches({"campus": "ERICA"}) and p.matches({"campus": "ALL"}) and p.matches({}) and not p.matches({"campus": "SEOUL"})
    assert p.explain({"campus": "SEOUL"}) == "campus=seoul not in ['erica', 'all']"
    assert FilterCriteria(audience="international").to_filter().matches({"audience": "[undergraduate, international]"})
    assert FilterCriteria().to_filter() is None


async def test_evidence_selection_methods(services):
    items = evidence(["one two", "one two", "three four five six"])
    assert [e.chunk_id for e in await TopKSelector({"top_k": 2}, services).select(items)] == ["c1", "c2"]
    from app.rag.blocks.evidence.evidence_selection.token_budget_selector import TokenBudgetSelector

    deduped = await TokenBudgetSelector({"max_evidence_tokens": 100, "deduplicate": True}, services).select(items)
    assert [e.chunk_id for e in deduped] == ["c1", "c3"]


async def test_sufficiency_gate_decisions(services):
    gate = ScoreThresholdChecker({"signal": "query_coverage", "threshold": 0.3, "on_missing_signal": "abstain"}, services)
    assert not (await gate.check(QUESTION, [])).sufficient
    yes = await gate.check(QUESTION, evidence(["scholarship documents needed"]))
    assert yes.sufficient and yes.signals["observed"] >= 0.3 and "≥" in yes.reason
    assert not (await gate.check(QUESTION, evidence(["campus map"]))).sufficient
    dense = ScoreThresholdChecker({"signal": "dense_similarity", "threshold": 0.95, "on_missing_signal": "proceed"}, services)
    assert not (await dense.check(QUESTION, evidence(["x"], [0.9]))).sufficient
    no_dense = [e.model_copy(update={"scores": {}}) for e in evidence(["x"])]
    assert (await dense.check(QUESTION, no_dense)).sufficient  # policy "proceed" when the signal is missing


async def test_gate_abstention_skips_generation(ingested, services, fake_ollama):
    config = validate_config({"evidence_sufficiency": {"method": "score_threshold", "params": {"threshold": 1.0}}})
    trace = await run_rag("zebra quantum volcano", config, services)
    assert trace["outcome"] == "insufficient_context" and fake_ollama.requests == []
    assert stages_of(trace)["generation"]["status"] == "skipped"


# ------------------------------------------------------------------ R14 and presets


def test_every_enabled_preset_resolves_to_implemented_methods():
    for p in PRESETS:
        if p.get("enabled", True):
            preset_config(p["id"])  # raises ConfigError otherwise


async def test_full_advanced_preset_runs_every_component(ingested, services, fake_ollama, monkeypatch):
    class FakeCrossEncoder:
        def predict(self, pairs, **kw):
            return [float(len(t)) for _, t in pairs]

    monkeypatch.setattr("app.rag.blocks.evidence.reranking.cross_encoder.load_cross_encoder", lambda device: FakeCrossEncoder())
    fake_ollama.answer = "need-based scholarship documents"
    trace = await run_rag(QUESTION, preset_config("R14_FULL_ADVANCED"), services)
    ran = [s["stage_id"] for s in trace["stages"] if s["status"] == "completed"]
    assert ran == ["query_rewriting", "dense_retrieval", "lexical_retrieval", "hybrid_fusion", "metadata_enrichment", "reranking",
                   "evidence_selection", "evidence_sufficiency", "context_construction", "generation"]  # fmt: skip


async def test_stop_after_runs_no_llm_and_saves_no_trace(ingested, services, fake_ollama, db):
    trace = await run_rag(QUESTION, validate_config({}), services, stop_after="evidence_sufficiency", save_trace=False)
    assert trace["outcome"] == "stopped" and fake_ollama.requests == [] and db.get_trace(trace["request_id"]) is None
    assert stages_of(trace)["generation"]["status"] == "skipped" and stages_of(trace)["evidence_selection"]["status"] == "completed"
