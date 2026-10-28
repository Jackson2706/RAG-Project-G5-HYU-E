from __future__ import annotations

import pytest

from app.models.config import ImplementationStatus, PipelineConfig, Scope, StageConfig
from app.rag import registry as r


def draft(**stages) -> PipelineConfig:
    return PipelineConfig(stages={k: StageConfig(**v) for k, v in stages.items()})


def messages(result) -> str:
    return " | ".join(e.message for e in result.errors)


def test_registry_lists_every_required_stage_in_order():
    payload = r.registry_payload()
    assert payload["offline_order"] == ["document_loading", "parsing", "chunking", "metadata_extraction", "embedding", "vector_indexing"]
    assert payload["online_order"] == [
        "query_understanding", "query_rewriting", "constraint_validation", "metadata_filtering", "dense_retrieval",
        "lexical_retrieval", "hybrid_fusion", "metadata_enrichment", "reranking", "evidence_selection", "sufficiency_gate",
        "context_builder", "generation", "citation_verification", "response_guard",
    ]  # fmt: skip
    for stage in payload["stages"]:
        assert stage["available_methods"] and stage["implementation_status"] in {"implemented", "planned", "unavailable"}
        if stage["category"] == "online":
            assert set(stage["input_schema"]) == set(stage["reads"])


def test_default_methods_are_implemented_and_defaults_validate():
    for spec in r.STAGES.values():
        method = spec.method(spec.selected_method)
        if spec.enabled:
            assert method.status is ImplementationStatus.implemented, spec.stage_id
        for p in method.parameters:
            assert p.validate_value(p.default) == p.default
    result = r.resolve_config(r.default_config())
    assert result.valid and not result.warnings


def test_partial_draft_is_filled_with_defaults():
    result = r.resolve_config(draft(dense_retrieval={"params": {"top_k": 25}}))
    assert result.valid
    dense = result.resolved.stage("dense_retrieval")
    assert dense.params["top_k"] == 25 and dense.params["exact"] is False and dense.method == "qdrant_cosine"


def test_planned_method_cannot_be_executed():
    result = r.resolve_config(draft(reranking={"enabled": True, "method": "cross_encoder"}))
    assert not result.valid and "planned" in messages(result)
    # ...but selecting it while the stage is disabled is allowed (shown, not run)
    assert r.resolve_config(draft(reranking={"enabled": False, "method": "cross_encoder"})).valid


@pytest.mark.parametrize(
    "params, fragment",
    [({"top_k": 0}, "≥ 1"), ({"top_k": 1000}, "≤ 100"), ({"top_k": 2.5}, "integer"), ({"exact": "yes"}, "true or false"),
     ({"score_threshold": 1.5}, "≤ 1")],
)  # fmt: skip
def test_parameter_validation(params, fragment):
    result = r.resolve_config(draft(dense_retrieval={"params": params}))
    assert not result.valid and fragment in messages(result)


def test_enum_and_multi_enum_validation():
    assert "not one of" in messages(r.resolve_config(draft(metadata_filtering={"enabled": True, "params": {"campus": "BUSAN"}})))
    assert "unknown value" in messages(r.resolve_config(draft(metadata_filtering={"params": {"audience": ["robots"]}})))


def test_unknown_params_and_stages():
    result = r.resolve_config(draft(dense_retrieval={"params": {"bogus": 1}}))
    assert result.valid and result.warnings[0].param == "bogus"
    assert "Unknown stage" in messages(r.resolve_config(draft(nonexistent={})))
    assert "Unknown method" in messages(r.resolve_config(draft(dense_retrieval={"method": "faiss"})))


def test_required_stage_cannot_be_disabled():
    assert "cannot be disabled" in messages(r.resolve_config(draft(generation={"enabled": False})))


def test_cross_stage_retriever_and_fusion_rules():
    assert "choose RRF" in messages(r.resolve_config(draft(lexical_retrieval={"enabled": True})))
    assert r.resolve_config(draft(lexical_retrieval={"enabled": True}, hybrid_fusion={"method": "rrf"})).valid
    assert "needs both" in messages(r.resolve_config(draft(hybrid_fusion={"method": "rrf"})))
    assert "at least one retriever" in messages(r.resolve_config(draft(dense_retrieval={"enabled": False})))
    assert r.resolve_config(draft(dense_retrieval={"enabled": False}, lexical_retrieval={"enabled": True})).valid


def test_chunking_constraints():
    assert "Overlap" in messages(r.resolve_config(draft(chunking={"params": {"chunk_size": 64, "chunk_overlap": 64}})))
    assert "min_chunk_size" in messages(r.resolve_config(draft(chunking={"params": {"chunk_size": 64, "max_chunk_size": 64, "min_chunk_size": 80}})))


def test_snapshot_is_frozen_and_hash_is_stable():
    a = r.resolve_config(draft(generation={"params": {"temperature": 0.7}})).resolved
    b = r.resolve_config(draft(generation={"params": {"temperature": 0.7}})).resolved
    c = r.resolve_config(draft(generation={"params": {"temperature": 0.1}})).resolved
    assert a.config_hash == b.config_hash != c.config_hash
    with pytest.raises(Exception):
        a.stage("generation").method = "other"  # type: ignore[misc]


def test_reindexing_scopes():
    emb = r.STAGES["embedding"].method("sentence_transformers")
    scopes = {p.name: p.scope for p in emb.parameters}
    assert scopes["model_id"] is Scope.index and scopes["normalize"] is Scope.index and scopes["batch_size"] is Scope.ingestion
    assert r.STAGES["embedding"].requires_reindexing and r.STAGES["chunking"].requires_reindexing
    online_scopes = {p.scope for s in r.ONLINE_STAGES for m in s.available_methods for p in m.parameters}
    assert online_scopes == {Scope.runtime}


def test_offline_differences_are_reported():
    resolved = r.resolve_config(draft(chunking={"params": {"chunk_size": 128}})).resolved
    active = r.resolve_config(r.default_config()).resolved
    issues = r.offline_config_differences(resolved, {k: v.model_dump() for k, v in active.stages.items()})
    assert [i.stage_id for i in issues] == ["chunking"]


def test_presets_marked_unavailable_when_they_need_planned_methods():
    availability = {p.preset_id: r.preset_availability(p) for p in r.BUILTIN_PRESETS}
    assert availability["baseline_dense"].available and availability["hybrid"].available and availability["metadata_aware"].available
    assert not availability["advanced"].available and "Cross-encoder" in availability["advanced"].unavailable_reason
