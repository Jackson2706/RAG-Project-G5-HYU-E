"""Tests for app/rag/registry.py."""

import inspect

import pytest

from app.rag import registry
from app.rag.blocks.retrieval import BaseDenseRetriever, QdrantDenseRetriever
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


def test_every_required_block_has_an_abstract_class():
    names = {s.base_class.__name__ for s in PIPELINE}
    assert names == {
        "BaseDocumentLoader", "BaseDocumentParser", "BaseChunker", "BaseMetadataExtractor", "BaseEmbedder", "BaseVectorIndexer",
        "BaseQueryUnderstanding", "BaseQueryRewriter", "BaseConstraintValidator", "BaseMetadataFilter", "BaseDenseRetriever",
        "BaseLexicalRetriever", "BaseHybridFusion", "BaseMetadataEnricher", "BaseReranker", "BaseEvidenceSelector",
        "BaseSufficiencyGate", "BaseContextBuilder", "BaseGenerator", "BaseCitationVerifier", "BaseResponseGuard"}  # fmt: skip


def test_defaults_are_valid_and_planned_stages_are_off():
    config = validate_config({})
    assert config["dense_retrieval"] == {"method": "qdrant_cosine", "params": {"top_k": 5}}
    assert config["reranking"] == {"method": None, "params": {}}
    assert config["chunking"]["params"] == {"chunk_size": 256, "chunk_overlap": 32}


def test_planned_methods_cannot_be_selected_or_created(services):
    assert "not implemented yet" in errors_of({"reranking": {"method": "cross_encoder"}})
    with pytest.raises(NotImplementedError):
        create_block("reranking", "cross_encoder", {}, services)


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
    assert "Unknown stage" in errors_of({"nonsense": {}})


def test_registry_json_has_no_python_objects_and_marks_status():
    data = registry_json()
    stages = {s["stage_id"]: s for s in data["stages"]}
    assert stages["dense_retrieval"]["implemented"] and not stages["reranking"]["implemented"]
    assert stages["reranking"]["methods"][0]["class_name"] == "CrossEncoderReranker"
    assert stages["generation"]["methods"][0]["parameters"]["model"]["ui"] == "ollama_model"
    assert stages["chunking"]["methods"][0]["parameters"]["chunk_size"]["scope"] == "ingestion"
    import json

    json.dumps(data)  # fully serializable


class StubRetriever(BaseDenseRetriever):
    async def retrieve(self, query, filters=None):
        return RetrievalResult(candidates=[])


@pytest.fixture
def extra_method():
    """Temporarily register a new dense retrieval method, like a student would."""
    stage = STAGES["dense_retrieval"]
    method = Method("stub_dense", "Stub dense", StubRetriever, True, "Test method",
                    parameters={"top_k": Param("integer", 3, "Top K", "How many", min=1, max=10)})  # fmt: skip
    stage.methods.append(method)
    yield method
    stage.methods.remove(method)


def test_a_new_method_appears_in_the_api_and_can_be_selected(extra_method, services):
    dense = next(s for s in registry_json()["stages"] if s["stage_id"] == "dense_retrieval")
    assert "stub_dense" in [m["method_id"] for m in dense["methods"]]
    config = validate_config({"dense_retrieval": {"method": "stub_dense", "params": {"top_k": 7}}})
    block = create_block("dense_retrieval", "stub_dense", config["dense_retrieval"]["params"], services)
    assert isinstance(block, StubRetriever) and block.params == {"top_k": 7} and block.method_id == "stub_dense"


def test_registry_check_catches_mistakes(monkeypatch):
    stage = STAGES["dense_retrieval"]
    wrong = Method("wrong_base", "Wrong", registry.MongoChunkLookup, True, "inherits from the wrong class")
    stage.methods.append(wrong)
    try:
        with pytest.raises(TypeError, match="must inherit from BaseDenseRetriever"):
            check_registry()
    finally:
        stage.methods.remove(wrong)
    duplicate = Method("qdrant_cosine", "Again", QdrantDenseRetriever, True, "duplicate id")
    stage.methods.append(duplicate)
    try:
        with pytest.raises(TypeError, match="duplicate method id"):
            check_registry()
    finally:
        stage.methods.remove(duplicate)
