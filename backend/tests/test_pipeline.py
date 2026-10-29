"""Tests for ingestion and the question-answering pipeline (real blocks, fake services)."""

import pytest
from qdrant_client import models

from app.rag.blocks.retrieval.dense_retrieval.base import BaseDenseRetriever
from app.rag.blocks.metadata_filtering.metadata_postfiltering.base import BaseMetadataPostfilter
from app.rag.blocks.metadata_filtering.metadata_prefiltering.base import BaseMetadataPrefilter
from app.rag.pipeline import run_ingestion, run_rag
from app.rag.registry import STAGES, Method, Param, validate_config
from app.rag.schemas import INSUFFICIENT_ANSWER, Candidate, PostfilterResult, RemovedCandidate, RetrievalFilter, RetrievalResult

pytestmark = pytest.mark.anyio
QUESTION = "What documents do I need for the need-based scholarship?"


def stages_of(trace):
    return {s["stage_id"]: s for s in trace["stages"]}


class temporarily_registered:
    """Register a test method for one test, like a student would in registry.py."""

    def __init__(self, stage_id: str, method: Method) -> None:
        self.stage, self.method = STAGES[stage_id], method

    def __enter__(self):
        self.stage.methods.append(self.method)

    def __exit__(self, *exc):
        self.stage.methods.remove(self.method)


# ------------------------------------------------------------------ ingestion


async def test_ingestion_links_mongodb_and_qdrant(ingested, db, fake_model):
    assert ingested["documents"] == 5 and ingested["errors"] == [] and ingested["dimension"] == fake_model.dim
    chunk_ids = {c["chunk_id"] for c in db.chunks.find()}
    points, _ = db.qdrant.scroll(db.collection, limit=1000, with_payload=True)
    assert {str(p.id) for p in points} == chunk_ids  # Qdrant point ID == MongoDB chunk_id
    assert {p.payload["doc_id"] for p in points} <= {d["doc_id"] for d in db.documents.find()}
    assert db.vector_size() == fake_model.dim
    assert db.index_info()["chunking"] == {"method": "section_tokens", "chunk_size": 256, "chunk_overlap": 32}


async def test_reingesting_gives_the_same_ids_and_bad_files_are_reported(ingested, corpus, db, services):
    first = sorted(c["chunk_id"] for c in db.chunks.find())
    (corpus / "broken.pdf").write_bytes(b"%PDF-1.4 not a pdf")
    report = run_ingestion(corpus, validate_config({}), services)
    assert sorted(c["chunk_id"] for c in db.chunks.find()) == first
    assert any("broken.pdf" in e for e in report["errors"])


# ------------------------------------------------------------------ basic RAG


async def test_basic_rag_answers_with_real_source_references(ingested, db, services, fake_ollama):
    events = []
    trace = await run_rag(QUESTION, validate_config({"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 3}}}),
                          services, emit=events.append)  # fmt: skip
    assert trace["status"] == "completed" and trace["outcome"] == "answered", trace["error"]
    cited = [s for s in trace["sources"] if s["cited"]]
    assert cited and db.chunks.find_one({"chunk_id": cited[0]["chunk_id"]})  # a real chunk record
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
    assert ran == ["dense_retrieval", "metadata_enrichment", "evidence_selection", "context_construction", "generation"]
    dense = s["dense_retrieval"]
    assert dense["method_id"] == "qdrant_cosine" and dense["params"] == {"top_k": 2} and dense["input"]["query"] == QUESTION
    assert len(dense["output"]["candidates"]) == 2 and dense["duration_ms"] is not None
    assert [e["chunk_id"] for e in s["metadata_enrichment"]["output"]] == [c["chunk_id"] for c in dense["output"]["candidates"]]
    assert s["generation"]["method_id"] == "ollama_chat" and s["generation"]["output"]["model"] == "test-model"


async def test_planned_stages_are_skipped_without_fake_output(ingested, services):
    trace = await run_rag(QUESTION, validate_config({}), services)
    s = stages_of(trace)
    for stage_id in ("query_understanding", "query_rewriting", "metadata_prefiltering", "lexical_retrieval", "hybrid_fusion",
                     "metadata_postfiltering", "reranking", "evidence_sufficiency"):  # fmt: skip
        assert s[stage_id]["status"] == "skipped" and s[stage_id]["output"] is None and s[stage_id]["method_id"] is None
        assert s[stage_id]["summary"] == "Not implemented yet."


class FirstChunkRetriever(BaseDenseRetriever):
    """A test method: always returns the first stored chunk."""

    async def retrieve(self, query, prefilter=None):
        chunk = self.services.db.chunks.find_one(sort=[("chunk_id", 1)])
        return RetrievalResult(candidates=[Candidate(rank=1, chunk_id=chunk["chunk_id"], doc_id=chunk["doc_id"], score=1.0)], details={"note": "test"})


async def test_the_selected_registered_method_is_executed(ingested, services):
    method = Method("first_chunk", "First chunk", FirstChunkRetriever, True, "test", {"top_k": Param("integer", 1, "Top K", "x", min=1, max=5)})
    with temporarily_registered("dense_retrieval", method):
        trace = await run_rag(QUESTION, validate_config({"dense_retrieval": {"method": "first_chunk"}}), services)
    dense = stages_of(trace)["dense_retrieval"]
    assert dense["method_id"] == "first_chunk" and dense["method_name"] == "First chunk"
    assert dense["output"]["details"] == {"note": "test"} and len(dense["output"]["candidates"]) == 1


# ------------------------------------------------------------------ prefiltering vs postfiltering


def one_document(db) -> str:
    return db.documents.find_one({"source_uri": {"$regex": "erica_housing"}})["doc_id"]


class OnlyOneDocumentPrefilter(BaseMetadataPrefilter):
    """Test prefilter: an eligibility predicate on the doc_id payload field."""

    async def build_filter(self, criteria):
        return RetrievalFilter(conditions={"doc_id": [self.params["doc_id"]]}, include_unknown=False)


class DropOneDocumentPostfilter(BaseMetadataPostfilter):
    """Test postfilter: removes candidates of one document from the retrieved list."""

    async def filter_candidates(self, candidates, criteria):
        drop = self.params["doc_id"]
        return PostfilterResult(kept=[c for c in candidates if c.doc_id != drop],
                                removed=[RemovedCandidate(chunk_id=c.chunk_id, reason="test: ineligible document") for c in candidates if c.doc_id == drop])  # fmt: skip


def doc_param(default: str) -> dict:
    return {"doc_id": Param("string", default, "Document", "test", ui="text")}


async def test_prefiltering_is_a_predicate_applied_inside_retrieval(ingested, db, services):
    erica = one_document(db)
    with temporarily_registered("metadata_prefiltering", Method("only_one_doc", "Only one doc", OnlyOneDocumentPrefilter, True, "test", doc_param(erica))):
        trace = await run_rag(QUESTION, validate_config({"metadata_prefiltering": {"method": "only_one_doc"},
                                                         "dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 3}}}), services)  # fmt: skip
    s = stages_of(trace)
    predicate = s["metadata_prefiltering"]["output"]
    assert predicate == {"conditions": {"doc_id": [erica]}, "include_unknown": False}
    dense = s["dense_retrieval"]
    assert dense["input"]["prefilter"] == predicate and dense["output"]["applied_filter"] == predicate  # retrieval reports the predicate it used
    # The question is about scholarships, yet every candidate is from the eligible document: Qdrant searched only that subset,
    # and still returned top_k candidates (no starvation).
    assert len(dense["output"]["candidates"]) == 3 and {c["doc_id"] for c in dense["output"]["candidates"]} == {erica}
    assert s["metadata_postfiltering"]["status"] == "skipped"  # enabled independently


async def test_postfiltering_removes_from_the_retrieved_list_and_can_starve(ingested, db, services):
    plain = await run_rag(QUESTION, validate_config({"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 3}}}), services)
    retrieved = stages_of(plain)["dense_retrieval"]["output"]["candidates"]
    top_doc = retrieved[0]["doc_id"]
    with temporarily_registered("metadata_postfiltering", Method("drop_doc", "Drop doc", DropOneDocumentPostfilter, True, "test", doc_param(top_doc))):
        trace = await run_rag(QUESTION, validate_config({"metadata_postfiltering": {"method": "drop_doc"},
                                                         "dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 3}}}), services)  # fmt: skip
    s = stages_of(trace)
    post = s["metadata_postfiltering"]
    assert post["input"]["candidates"] == s["dense_retrieval"]["output"]["candidates"]  # it received the retrieved candidates
    kept_ids = [c["chunk_id"] for c in post["output"]["kept"]]
    assert all(c["doc_id"] != top_doc for c in post["output"]["kept"])
    assert len(kept_ids) + len(post["output"]["removed"]) == 3  # nothing new was searched: fewer than top_k may remain
    assert [e["chunk_id"] for e in s["metadata_enrichment"]["output"]] == kept_ids
    assert s["metadata_prefiltering"]["status"] == "skipped"


async def test_disabled_filtering_does_not_change_dense_retrieval(ingested, services):
    a = await run_rag(QUESTION, validate_config({}), services)
    b = await run_rag(QUESTION, validate_config({"metadata_prefiltering": {"method": None}, "metadata_postfiltering": {"method": None}}), services)
    assert stages_of(a)["dense_retrieval"]["output"] == stages_of(b)["dense_retrieval"]["output"]
    assert stages_of(a)["dense_retrieval"]["input"]["prefilter"] is None


# ------------------------------------------------------------------ abstention and errors


async def test_empty_retrieval_abstains_without_calling_the_model(db, services, fake_ollama, fake_model):
    db.qdrant.create_collection(db.collection, vectors_config=models.VectorParams(size=fake_model.dim, distance=models.Distance.COSINE))
    trace = await run_rag("Anything?", validate_config({}), services)
    s = stages_of(trace)
    assert trace["outcome"] == "insufficient_context" and trace["answer"] == INSUFFICIENT_ANSWER
    assert s["generation"]["status"] == "skipped" and "abstention" in s["generation"]["summary"]
    assert fake_ollama.requests == []


async def test_model_saying_insufficient_context(ingested, services, fake_ollama):
    fake_ollama.answer = "INSUFFICIENT_CONTEXT\nThe evidence does not mention parking."
    trace = await run_rag("Where can I park?", validate_config({}), services)
    assert trace["outcome"] == "insufficient_context" and "parking" in trace["answer"] and trace["sources"] == []


async def test_made_up_source_labels_are_removed(ingested, services, fake_ollama):
    fake_ollama.answer = "A fact [E1]. Made up [E9]."
    trace = await run_rag(QUESTION, validate_config({}), services)
    assert "[E9]" not in trace["answer"] and "[E1]" in trace["answer"]
    assert [s["label"] for s in trace["sources"] if s["cited"]] == ["E1"]


async def test_a_failing_stage_is_recorded(ingested, services, fake_ollama):
    fake_ollama.fail = "500"
    trace = await run_rag(QUESTION, validate_config({}), services)
    assert trace["status"] == "failed" and "500" in trace["error"]
    assert trace["stages"][-1]["stage_id"] == "generation" and trace["stages"][-1]["status"] == "failed"


async def test_no_index_gives_a_clear_error(services):
    trace = await run_rag(QUESTION, validate_config({}), services)
    assert trace["status"] == "failed" and "No documents are indexed" in trace["error"]
