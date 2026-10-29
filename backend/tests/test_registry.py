"""Tests for app/rag/registry.py."""

import inspect
import json

import pytest

from app.rag.blocks.retrieval.dense_retrieval.base import BaseDenseRetriever
from app.rag.blocks.retrieval.dense_retrieval.qdrant_cosine import QdrantDenseRetriever
from app.rag.blocks.evidence.metadata_enrichment.mongodb_enrichment import MongoChunkLookup
from app.rag.registry import PIPELINE, STAGES, ConfigError, Method, Param, check_registry, create_block, registry_json, validate_config
from app.rag.schemas import RetrievalResult


def errors_of(draft) -> str:
    with pytest.raises(ConfigError) as info:
        validate_config(draft)
    return " | ".join(e["message"] for e in info.value.errors)


def test_method_ids_are_unique_and_classes_inherit_correctly():
    ids = [m.method_id for s in PIPELINE for m in s.methods]
    assert len(ids) == len(set(ids))
    for stage in PIPELINE:
        for m in stage.methods:
            assert issubclass(m.cls, stage.base_class) and not inspect.isabstract(m.cls)
    check_registry()  # also runs at import


def test_blocks_follow_the_course_pipeline():
    online = [s.stage_id for s in PIPELINE if s.phase == "online"]
    assert online == ["query_understanding", "query_rewriting", "metadata_prefiltering", "dense_retrieval", "lexical_retrieval",
                      "hybrid_fusion", "metadata_postfiltering", "metadata_enrichment", "reranking", "evidence_selection",
                      "evidence_sufficiency", "context_construction", "generation"]  # fmt: skip
    offline = [s.stage_id for s in PIPELINE if s.phase == "offline"]
    assert offline == ["document_loading", "parsing", "chunking", "metadata_extraction", "embedding", "vector_indexing"]
    assert not {"citation_verification", "response_guard", "constraint_validation"} & set(STAGES)


def test_defaults_are_valid_and_planned_stages_are_off():
    config = validate_config({})
    assert config["dense_retrieval"] == {"method": "qdrant_cosine", "params": {"top_k": 5}}
    for stage_id in ("metadata_prefiltering", "metadata_postfiltering", "reranking"):
        assert config[stage_id] == {"method": None, "params": {}}
    assert config["chunking"]["params"] == {"chunk_size": 256, "chunk_overlap": 32}


def test_planned_methods_cannot_be_selected_or_created(services):
    assert "not implemented yet" in errors_of({"metadata_prefiltering": {"method": "qdrant_prefilter"}})
    assert "not implemented yet" in errors_of({"metadata_postfiltering": {"method": "candidate_postfilter"}})
    with pytest.raises(NotImplementedError):
        create_block("metadata_prefiltering", "qdrant_prefilter", {}, services)
    with pytest.raises(NotImplementedError):
        create_block("metadata_postfiltering", "candidate_postfilter", {}, services)


@pytest.mark.parametrize("params, message", [
    ({"top_k": 0}, "at least 1"), ({"top_k": 99}, "at most 20"), ({"top_k": 2.5}, "whole number"),
    ({"top_k": "five"}, "number"), ({"topk": 5}, "no parameter 'topk'"),
])  # fmt: skip
def test_hyperparameters_are_validated(params, message):
    assert message in errors_of({"dense_retrieval": {"method": "qdrant_cosine", "params": params}})


def test_combination_rules():
    assert "smaller than chunk size" in errors_of({"chunking": {"method": "section_tokens", "params": {"chunk_size": 64, "chunk_overlap": 64}}})
    assert "at least one retriever" in errors_of({"dense_retrieval": {"method": None}})
    assert "needs a method" in errors_of({"generation": {"method": None}})
    assert "Unknown stage" in errors_of({"citation_verification": {}})


def test_registry_json_is_serializable_and_marks_status():
    data = registry_json()
    json.dumps(data)
    stages = {s["stage_id"]: s for s in data["stages"]}
    assert stages["metadata_prefiltering"]["base_class"] == "BaseMetadataPrefilter"
    assert stages["metadata_postfiltering"]["methods"][0]["file"] == "metadata_filtering/metadata_postfiltering/candidate_postfilter.py"
    assert stages["generation"]["methods"][0]["parameters"]["model"]["ui"] == "ollama_model"
    assert stages["chunking"]["methods"][0]["parameters"]["chunk_size"]["scope"] == "ingestion"


class StubRetriever(BaseDenseRetriever):
    async def retrieve(self, query, prefilter=None):
        return RetrievalResult(candidates=[])


def test_a_new_method_appears_in_the_api_and_can_be_selected(services):
    stage = STAGES["dense_retrieval"]
    method = Method("stub_dense", "Stub dense", StubRetriever, True, "Test method",
                    parameters={"top_k": Param("integer", 3, "Top K", "How many", min=1, max=10)})  # fmt: skip
    stage.methods.append(method)
    try:
        dense = next(s for s in registry_json()["stages"] if s["stage_id"] == "dense_retrieval")
        assert "stub_dense" in [m["method_id"] for m in dense["methods"]]
        config = validate_config({"dense_retrieval": {"method": "stub_dense", "params": {"top_k": 7}}})
        block = create_block("dense_retrieval", "stub_dense", config["dense_retrieval"]["params"], services)
        assert isinstance(block, StubRetriever) and block.params == {"top_k": 7} and block.method_id == "stub_dense"
    finally:
        stage.methods.remove(method)


@pytest.mark.parametrize("method, message", [
    (Method("wrong_base", "Wrong", MongoChunkLookup, True, "x"), "must inherit from BaseDenseRetriever"),
    (Method("qdrant_cosine", "Again", QdrantDenseRetriever, True, "x"), "duplicate method id"),
    (Method("bad_default", "Bad", StubRetriever, True, "x", {"top_k": Param("integer", 50, "Top K", "x", min=1, max=10)}), "default of 'bad_default.top_k'"),
])  # fmt: skip
def test_registry_check_catches_mistakes(method, message):
    stage = STAGES["dense_retrieval"]
    stage.methods.append(method)
    try:
        with pytest.raises(TypeError, match=message):
            check_registry()
    finally:
        stage.methods.remove(method)
