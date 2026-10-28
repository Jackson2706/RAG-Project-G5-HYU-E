from __future__ import annotations

import pytest

from app.models.documents import Chunk, SourceDocument, SourceSpan
from app.models.pipeline import Candidate, Citation, MetadataFilterSpec
from app.rag import generation as gen
from app.rag.retrieval import BM25Index, build_qdrant_filter, fuse, matches_filter
from tests.conftest import RegexTokenizer, online

pytestmark = pytest.mark.anyio


def cand(cid, dense=None, lexical=None, text="t", tokens=10):
    return Candidate(chunk_id=cid, doc_id="d", dense_score=dense[0] if dense else None, dense_rank=dense[1] if dense else None,
                     lexical_score=lexical[0] if lexical else None, lexical_rank=lexical[1] if lexical else None,
                     text=text, token_count=tokens)  # fmt: skip


# ------------------------------------------------------------------ fusion / filters / BM25


def test_rrf_uses_ranks_only():
    dense = [cand("a", (0.9, 1)), cand("b", (0.8, 2))]
    lexical = [cand("b", lexical=(12.0, 1)), cand("c", lexical=(3.0, 2))]
    out = fuse(dense, lexical, "rrf", {"rrf_k": 60, "candidate_limit": 10})
    assert [c.chunk_id for c in out] == ["b", "a", "c"]
    assert out[0].fused_score == pytest.approx(1 / 62 + 1 / 61, abs=1e-6)
    assert out[0].dense_rank == 2 and out[0].lexical_rank == 1  # per-retriever ranks preserved


def test_weighted_fusion_and_limit():
    dense = [cand("a", (0.9, 1)), cand("b", (0.5, 2))]
    lexical = [cand("b", lexical=(10.0, 1)), cand("a", lexical=(0.0, 2))]
    out = fuse(dense, lexical, "weighted", {"dense_weight": 0.8, "candidate_limit": 1})
    assert [c.chunk_id for c in out] == ["a"] and out[0].fused_score == pytest.approx(0.8)


def test_no_fusion_preserves_order():
    out = fuse([cand("x", (0.2, 1)), cand("y", (0.1, 2))], [], "none", {})
    assert [(c.chunk_id, c.fused_rank) for c in out] == [("x", 1), ("y", 2)]


def test_filter_semantics_unknown_and_university_wide():
    spec = MetadataFilterSpec(campus="ERICA")
    assert matches_filter({"campus": "ERICA"}, spec)
    assert matches_filter({"campus": "ALL"}, spec)
    assert matches_filter({"campus": None}, spec)
    assert not matches_filter({"campus": "SEOUL"}, spec)
    strict = MetadataFilterSpec(campus="ERICA", include_unknown=False, include_university_wide=False)
    assert not matches_filter({"campus": None}, strict) and not matches_filter({"campus": "ALL"}, strict)
    assert build_qdrant_filter(MetadataFilterSpec()) is None


def test_audience_hierarchy_freshman_inherits_undergraduate_documents():
    spec = MetadataFilterSpec(audience=["freshman"])
    assert matches_filter({"audience": ["undergraduate"]}, spec)
    assert matches_filter({"audience": ["all"]}, spec)
    assert not matches_filter({"audience": ["graduate"]}, spec)


def test_bm25_ranks_term_matches():
    def ch(i, text):
        return Chunk(chunk_id=f"c{i}", doc_id="d", version_id="v", chunk_index=i, text=text, source_span=SourceSpan(start=0, end=len(text)),
                     token_count=5, chunker_id="x", chunker_config_hash="h")  # fmt: skip

    idx = BM25Index([ch(0, "scholarship application deadline"), ch(1, "dormitory move-in checklist"), ch(2, "scholarship types")], True, "r")
    hits, terms = idx.search("How do I apply for a scholarship application?", 5, 1.5, 0.75, None)
    assert terms == ["apply", "scholarship", "application"]
    assert [c.chunk_id for c, _ in hits] == ["c0", "c2"]


async def test_qdrant_side_filter_excludes_other_campus(ingested, pipeline):
    trace = await pipeline.run("dormitory application", online({"metadata_filtering": {"enabled": True, "params": {"campus": "SEOUL"}}}))
    dense = next(s for s in trace.stages if s.stage_id == "dense_retrieval")
    campuses = {c["payload"].get("campus") for c in dense.output["candidates"]}
    assert "ERICA" not in campuses and campuses <= {"SEOUL", "ALL", None}
    assert dense.input["filter"] is not None


# ------------------------------------------------------------------ evidence & citations


def test_context_builder_labels_and_budget():
    ev = [Candidate(chunk_id=f"c{i}", doc_id="d", text=" ".join(["word"] * 100), title="Doc", section_path=["Doc", "Sec"], page_number=2)
          for i in range(3)]  # fmt: skip
    text, citations, stats = gen.build_context(ev, "standard", {"include_source_metadata": True, "max_context_tokens": 300}, RegexTokenizer())
    assert text.startswith("[S1] Doc — Sec — page 2")
    assert [c.marker for c in citations] == ["S1", "S2", "S3"][: len(citations)]
    assert stats["context_tokens"] <= 300 and (stats["truncated"] or stats["dropped"])


def test_cited_marker_parsing_variants():
    assert gen.cited_markers("A [S1]. B [S2, S3]. C [S4][S1]. D [S5; 6].") == ["S1", "S2", "S3", "S4", "S5", "S6"]


def test_verify_citations_identity_and_span():
    content = "Intro. Registration opens in February."
    chunk = Chunk(chunk_id="c1", doc_id="d1", version_id="v1", chunk_index=0, text="Registration opens in February.",
                  source_span=SourceSpan(start=7, end=38), token_count=5, chunker_id="x", chunker_config_hash="h")  # fmt: skip
    doc = SourceDocument(doc_id="d1", source_uri="local://x.md", file_path="x.md", media_type="text/markdown", size_bytes=1,
                         source_sha256="s", parser_id="p", version_id="v1", content=content)  # fmt: skip
    cites = [Citation(marker="S1", chunk_id="c1", doc_id="d1"), Citation(marker="S2", chunk_id="missing", doc_id="d9")]
    out, report = gen.verify_citations("Registration opens in February [S1]. Also see [S7].", cites, {"c1": chunk}, {"d1": doc}, True)
    assert out[0].cited and out[0].resolved and out[0].span_verified
    assert report.invalid_markers == ["S7"] and report.unresolved == ["S2"] and report.uncited_evidence == ["S2"]
    doc.content = "changed text that no longer matches the stored span"
    out, report = gen.verify_citations("x [S1]", cites[:1], {"c1": chunk}, {"d1": doc}, True)
    assert out[0].span_verified is False and report.span_failures == ["S1"]


# ------------------------------------------------------------------ pipeline


async def test_baseline_pipeline_end_to_end(ingested, pipeline, fake_ollama, repos):
    events = []

    async def emit(e):
        events.append(e)

    trace = await pipeline.run("When is the international student orientation session?", online(), session_id="s1", emit=emit)
    assert trace.status == "completed", trace.error
    statuses = {s.stage_id: s.status for s in trace.stages}
    assert statuses["dense_retrieval"] == statuses["generation"] == statuses["citation_verification"] == "completed"
    for disabled in ("query_rewriting", "metadata_filtering", "lexical_retrieval", "reranking"):
        assert statuses[disabled] == "bypassed"
    assert all(s.duration_ms is not None for s in trace.stages)
    result = trace.result
    assert result.outcome == "answered"
    cited = [c for c in result.citations if c.cited]
    assert cited and cited[0].marker == "S1" and cited[0].resolved and cited[0].span_verified
    # grounded prompt contains the evidence and the question
    sent = fake_ollama.requests[0]
    assert "[S1]" in sent["messages"][1]["content"] and "international student" in sent["messages"][1]["content"]
    assert "think" not in sent  # model has no thinking capability → option not sent
    types = [e.type for e in events]
    assert types[0] == "pipeline_started" and types[-1] == "pipeline_completed"
    assert "answer_delta" in types and types.index("answer_completed") < types.index("pipeline_completed")
    assert "".join(e.delta for e in events if e.type == "answer_delta").strip() == fake_ollama.answer
    stored = repos[0].get_trace(trace.request_id)
    assert stored.config.config_hash == trace.config.config_hash and len(stored.stages) == 15


async def test_thinking_models_get_think_false_and_thinking_is_not_streamed(ingested, pipeline, fake_ollama):
    fake_ollama.capabilities = ["completion", "thinking"]
    events = []

    async def emit(e):
        events.append(e)

    await pipeline.run("orientation schedule", online(), emit=emit)
    assert fake_ollama.requests[0]["think"] is False
    assert "private" not in "".join(e.delta or "" for e in events)


async def test_empty_retrieval_abstains_without_calling_llm(ingested, pipeline, fake_ollama):
    cfg = online({"dense_retrieval": {"params": {"score_threshold": 0.999}}})
    trace = await pipeline.run("completely unrelated question about volcanoes", cfg)
    statuses = {s.stage_id: s.status for s in trace.stages}
    assert statuses["sufficiency_gate"] == "completed" and statuses["generation"] == "bypassed"
    assert trace.result.outcome == "insufficient_evidence" and not fake_ollama.requests


async def test_model_reported_insufficient_context(ingested, pipeline, fake_ollama):
    fake_ollama.answer = "INSUFFICIENT_CONTEXT\nThe sources [S1] and [S2] do not mention parking."
    trace = await pipeline.run("Where can I park my car?", online())
    assert trace.result.outcome == "insufficient_evidence"
    assert "parking" in trace.result.answer
    assert trace.result.citations and not any(c.cited for c in trace.result.citations)


async def test_invalid_citation_markers_are_removed(ingested, pipeline, fake_ollama):
    fake_ollama.answer = "Registration has three periods [S1][S9]."
    trace = await pipeline.run("What are the course registration periods?", online())
    assert "[S9]" not in trace.result.answer and "[S1]" in trace.result.answer
    assert any("S9" in n for n in trace.result.guard_notes)


async def test_missing_citations_policy(ingested, pipeline, fake_ollama):
    fake_ollama.answer = "Registration has three periods."
    warn = await pipeline.run("registration periods", online())
    assert warn.result.outcome == "answered" and any("no valid citation" in n for n in warn.result.guard_notes)
    abstain = await pipeline.run("registration periods", online({"response_guard": {"params": {"on_missing_citations": "abstain"}}}))
    assert abstain.result.outcome == "abstained"


async def test_stage_failure_stops_downstream(ingested, pipeline, fake_ollama):
    fake_ollama.fail = "500"
    events = []

    async def emit(e):
        events.append(e)

    trace = await pipeline.run("orientation", online(), emit=emit)
    statuses = {s.stage_id: s.status for s in trace.stages}
    assert trace.status == "failed" and statuses["generation"] == "failed"
    assert statuses["citation_verification"] == statuses["response_guard"] == "pending"
    assert "500" in trace.error and trace.result is None
    assert events[-1].type == "pipeline_error" and events[-1].trace is not None


async def test_no_active_index_is_reported(pipeline):
    trace = await pipeline.run("anything", online())
    dense = next(s for s in trace.stages if s.stage_id == "dense_retrieval")
    assert dense.status == "failed" and "No active index" in dense.error


async def test_hybrid_pipeline_records_both_ranks(ingested, pipeline):
    cfg = online({"lexical_retrieval": {"enabled": True}, "hybrid_fusion": {"method": "rrf"}})
    trace = await pipeline.run("scholarship required documents", cfg)
    fusion = next(s for s in trace.stages if s.stage_id == "hybrid_fusion")
    assert fusion.status == "completed"
    assert any("dense_rank" in c and "lexical_rank" in c for c in fusion.output["candidates"])


async def test_detected_constraint_conflict_policy(ingested, pipeline):
    base = {"query_understanding": {"method": "rule_based"}, "constraint_validation": {"method": "deterministic"}}
    keep = online({**base, "metadata_filtering": {"enabled": True, "params": {"campus": "SEOUL"}}})
    trace = await pipeline.run("Dormitory on the ERICA campus?", keep)
    cv = next(s for s in trace.stages if s.stage_id == "constraint_validation")
    assert cv.output["filter_spec"]["campus"] == "SEOUL" and "conflict" in cv.output["notes"][0]
    reject = online({**base, "constraint_validation": {"method": "deterministic", "params": {"conflict_policy": "reject"}},
                     "metadata_filtering": {"enabled": True, "params": {"campus": "SEOUL"}}})  # fmt: skip
    trace = await pipeline.run("Dormitory on the ERICA campus?", reject)
    assert trace.status == "failed" and "Constraint conflict" in trace.error


async def test_detected_campus_becomes_filter(ingested, pipeline):
    cfg = online({"query_understanding": {"method": "rule_based"}, "metadata_filtering": {"enabled": True}})
    trace = await pipeline.run("How do international students apply for a dormitory at ERICA?", cfg)
    qu = next(s for s in trace.stages if s.stage_id == "query_understanding")
    assert qu.output["detected_constraints"] == {"campus": "ERICA", "audience": ["international"]}
    dense = next(s for s in trace.stages if s.stage_id == "dense_retrieval")
    assert "SEOUL" not in {c["payload"].get("campus") for c in dense.output["candidates"]}
