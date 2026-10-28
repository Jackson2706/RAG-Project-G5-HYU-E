"""Tests for ingestion and the question-answering pipeline (real blocks, fake services)."""

import pytest
from qdrant_client import models

from app.rag.blocks.retrieval import BaseDenseRetriever
from app.rag.blocks.verification import INSUFFICIENT_ANSWER
from app.rag.pipeline import run_ingestion, run_rag
from app.rag.registry import STAGES, Method, Param, validate_config
from app.rag.schemas import Candidate, RetrievalResult

pytestmark = pytest.mark.anyio
QUESTION = "What documents do I need for the need-based scholarship?"


def stages_of(trace):
    return {s["stage_id"]: s for s in trace["stages"]}


# ------------------------------------------------------------------ ingestion


async def test_ingestion_links_mongodb_and_qdrant(ingested, db, fake_model):
    assert ingested["documents"] == 5 and ingested["errors"] == [] and ingested["dimension"] == fake_model.dim
    chunk_ids = {c["chunk_id"] for c in db.chunks.find()}
    points, _ = db.qdrant.scroll(db.collection, limit=1000, with_payload=True)
    assert {str(p.id) for p in points} == chunk_ids  # Qdrant point ID == MongoDB chunk_id
    assert {p.payload["doc_id"] for p in points} <= {d["doc_id"] for d in db.documents.find()}
    assert db.vector_size() == fake_model.dim
    info = db.index_info()
    assert info["chunking"] == {"method": "section_tokens", "chunk_size": 256, "chunk_overlap": 32}


async def test_reingesting_gives_the_same_ids_and_bad_files_are_reported(ingested, corpus, db, services):
    first = sorted(c["chunk_id"] for c in db.chunks.find())
    (corpus / "broken.pdf").write_bytes(b"%PDF-1.4 not a pdf")
    report = run_ingestion(corpus, validate_config({}), services)
    assert sorted(c["chunk_id"] for c in db.chunks.find()) == first
    assert any("broken.pdf" in e for e in report["errors"])


# ------------------------------------------------------------------ the basic RAG pipeline


async def test_basic_rag_answers_with_real_citations(ingested, db, services, fake_ollama):
    events = []
    trace = await run_rag(QUESTION, validate_config({"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 3}}}),
                          services, emit=events.append)  # fmt: skip
    assert trace["status"] == "completed" and trace["outcome"] == "answered", trace["error"]
    cited = [c for c in trace["citations"] if c["cited"]]
    assert cited and db.chunks.find_one({"chunk_id": cited[0]["chunk_id"]})  # resolves to a real record
    assert db.documents.find_one({"doc_id": cited[0]["doc_id"]})["title"] == cited[0]["title"]
    prompt = fake_ollama.requests[0]["messages"][1]["content"]
    assert "[E1]" in prompt and "household income certificate" in prompt.lower()
    assert "".join(e["text"] for e in events if e["type"] == "answer_delta").strip() == trace["answer"]
    assert events[0]["type"] == "started" and events[-1]["type"] == "done"
    assert db.get_trace(trace["request_id"])["config"]["dense_retrieval"]["params"]["top_k"] == 3


async def test_trace_shows_real_inputs_outputs_methods_and_params(ingested, services):
    trace = await run_rag(QUESTION, validate_config({"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 2}}}), services)
    s = stages_of(trace)
    ran = [r["stage_id"] for r in trace["stages"] if r["status"] == "completed"]
    assert ran == ["dense_retrieval", "metadata_enrichment", "evidence_selection", "context_builder", "generation",
                   "citation_verification", "response_guard"]  # fmt: skip
    dense = s["dense_retrieval"]
    assert dense["method_id"] == "qdrant_cosine" and dense["params"] == {"top_k": 2} and dense["input"]["query"] == QUESTION
    assert len(dense["output"]["candidates"]) == 2 and dense["duration_ms"] is not None
    assert [e["chunk_id"] for e in s["metadata_enrichment"]["output"]] == [c["chunk_id"] for c in dense["output"]["candidates"]]
    assert s["generation"]["method_id"] == "ollama_chat" and s["generation"]["output"]["model"] == "test-model"


async def test_planned_stages_are_skipped_without_fake_output(ingested, services):
    trace = await run_rag(QUESTION, validate_config({}), services)
    s = stages_of(trace)
    for stage_id in ("query_rewriting", "lexical_retrieval", "hybrid_fusion", "reranking", "sufficiency_gate"):
        assert s[stage_id]["status"] == "skipped" and s[stage_id]["output"] is None and s[stage_id]["method_id"] is None
        assert s[stage_id]["summary"] == "Not implemented yet."


class FirstChunkRetriever(BaseDenseRetriever):
    """A test method: always returns the first stored chunk."""

    async def retrieve(self, query, filters=None):
        chunk = self.services.db.chunks.find_one(sort=[("chunk_id", 1)])
        return RetrievalResult([Candidate(1, chunk["chunk_id"], chunk["doc_id"], 1.0)], details={"note": "test"})


async def test_the_selected_registered_method_is_executed(ingested, services):
    stage = STAGES["dense_retrieval"]
    method = Method("first_chunk", "First chunk", FirstChunkRetriever, True, "test", {"top_k": Param("integer", 1, "Top K", "x", min=1, max=5)})
    stage.methods.append(method)
    try:
        trace = await run_rag(QUESTION, validate_config({"dense_retrieval": {"method": "first_chunk"}}), services)
    finally:
        stage.methods.remove(method)
    dense = stages_of(trace)["dense_retrieval"]
    assert dense["method_id"] == "first_chunk" and dense["method_name"] == "First chunk"
    assert dense["output"]["details"] == {"note": "test"} and len(dense["output"]["candidates"]) == 1


# ------------------------------------------------------------------ abstaining and errors


async def test_empty_retrieval_does_not_call_the_model(db, services, fake_ollama, fake_model):
    db.qdrant.create_collection(db.collection, vectors_config=models.VectorParams(size=fake_model.dim, distance=models.Distance.COSINE))
    trace = await run_rag("Anything?", validate_config({}), services)
    s = stages_of(trace)
    assert trace["outcome"] == "insufficient_context" and trace["answer"] == INSUFFICIENT_ANSWER
    assert s["generation"]["status"] == "skipped" and "no evidence" in s["generation"]["summary"]
    assert s["response_guard"]["status"] == "completed" and fake_ollama.requests == []


async def test_model_saying_insufficient_context(ingested, services, fake_ollama):
    fake_ollama.answer = "INSUFFICIENT_CONTEXT\nThe evidence does not mention parking."
    trace = await run_rag("Where can I park?", validate_config({}), services)
    assert trace["outcome"] == "insufficient_context" and "parking" in trace["answer"] and trace["citations"] == []


async def test_invalid_citation_markers_are_removed(ingested, services, fake_ollama):
    fake_ollama.answer = "A fact [E1]. Made up [E9]."
    trace = await run_rag(QUESTION, validate_config({}), services)
    assert "[E9]" not in trace["answer"] and stages_of(trace)["citation_verification"]["output"]["invalid_markers"] == ["E9"]


async def test_a_failing_stage_is_recorded(ingested, services, fake_ollama):
    fake_ollama.fail = "500"
    trace = await run_rag(QUESTION, validate_config({}), services)
    assert trace["status"] == "failed" and "500" in trace["error"]
    assert trace["stages"][-1]["stage_id"] == "generation" and trace["stages"][-1]["status"] == "failed"


async def test_no_index_gives_a_clear_error(services):
    trace = await run_rag(QUESTION, validate_config({}), services)
    assert trace["status"] == "failed" and "No documents are indexed" in trace["error"]
