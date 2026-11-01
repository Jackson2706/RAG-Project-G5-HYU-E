"""Tests for the runner's bookkeeping: IDs, resume, index reuse, missing labels and failure classification."""

import json
from argparse import Namespace

import mongomock
import pytest
from qdrant_client import QdrantClient

from evaluation import beir
from evaluation.failure_analysis import classify_fixture, classify_retrieval
from evaluation.indexes import corpus_checksum, is_current, offline_part
from evaluation.reports import generation_tables, write_reports
from evaluation.runner import Task, build_plan, depth_overrides, extract, load_yaml, read_done

from app.database import Database
from app.rag.presets import preset_config


def test_beir_document_ids_survive_the_round_trip():
    corpus = {"4983": {"title": "A title", "text": "Body."}, "doc/with/slash": {"title": "", "text": "x"}}
    docs = beir.to_parsed_documents("scifact", corpus)
    assert [beir.beir_id(d.source_uri) for d in docs] == ["4983", "doc/with/slash"]
    assert docs[0].full_text() == "A title\n\nBody." and docs[1].title == "doc/with/slash"


def test_extract_maps_chunks_to_original_ids_by_first_appearance():
    trace = {"status": "completed", "error": None, "total_ms": 5, "stages": [
        {"stage_id": "dense_retrieval", "status": "completed", "duration_ms": 1, "output": {"candidates": [], "details": {"search_ms": 1}}},
        {"stage_id": "metadata_enrichment", "status": "completed", "duration_ms": 1,
         "output": [{"doc_id": "u2", "token_count": 3}, {"doc_id": "u1", "token_count": 3}, {"doc_id": "u2", "token_count": 3}]},
        {"stage_id": "evidence_selection", "status": "completed", "duration_ms": 1, "output": [{"doc_id": "u2", "token_count": 3}]},
    ]}  # fmt: skip
    rec = extract(trace, {"u1": "beir-1", "u2": "beir-2"}, depth=100)
    assert rec["ranking"] == ["beir-2", "beir-1"] and rec["selected"] == ["beir-2"] and rec["units_ranked"] == 3


def test_resume_retries_failed_queries_only(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in [{"qid": "1", "status": "completed"}, {"qid": "2", "status": "failed"}]) + "\n")
    assert read_done(path) == {"1"}
    assert read_done(tmp_path / "missing.jsonl") == set()


def test_index_is_reused_only_for_the_same_config_and_corpus():
    db = Database(mongomock.MongoClient()["t"], QdrantClient(location=":memory:"), "c", "x")
    docs = beir.to_parsed_documents("scifact", {"1": {"title": "t", "text": "a"}})
    config = preset_config("O0_SECTION_AWARE_256_32")
    db.save_manifest({"config": offline_part(config), "corpus": {"checksum": corpus_checksum(docs)}})
    assert is_current(db, config, corpus_checksum(docs))
    assert not is_current(db, preset_config("O3_SMALL_CHUNKS"), corpus_checksum(docs))  # other chunk size → rebuild
    assert not is_current(db, config, corpus_checksum(beir.to_parsed_documents("scifact", {"1": {"title": "t", "text": "b"}})))


def test_plan_marks_inapplicable_and_shared_tasks_and_sets_depths():
    args = Namespace(suite="retrieval", dataset="scifact", experiment=None)
    tasks = {t.experiment + t.protocol: t for t in build_plan(args, load_yaml("offline.yaml"), load_yaml("online.yaml"), load_yaml("generation.yaml"))}
    assert tasks["R9_PREFILTERING-"].status == "NOT_APPLICABLE" and tasks["R0_DENSE-"].status == "SHARED"
    assert tasks["R6_QUERY_REWRITING" + "B"].query_limit == 100 and tasks["B0_BASIC_DENSE_RAG" + "A"].index_key == "whole_document"
    hybrid = Task("retrieval", "R2", "scifact", "B", "R2_HYBRID_RRF", options={"branch_depth_factor": 0.5})
    o = depth_overrides(preset_config("R2_HYBRID_RRF"), hybrid, {"documents": 100, "chunks": 600, "rerank": 100}, None)
    assert o["dense_retrieval"]["params"]["top_k"] == 300 and o["hybrid_fusion"]["params"]["top_k"] == 600
    rewrite = Task("retrieval", "R6", "scifact", "B", "R6_QUERY_REWRITING", options={"llm": True})
    assert depth_overrides(preset_config("R6_QUERY_REWRITING"), rewrite, {"documents": 100, "chunks": 600}, "qwen3.5:4b")["query_rewriting"] == {
        "params": {"model": "qwen3.5:4b"}}


def test_failure_classification_finds_the_earliest_stage():
    relevant = {"d1"}
    assert classify_retrieval({"status": "failed", "error": "OllamaError: down"}, relevant) == ["service_failure"]
    assert classify_retrieval({"status": "completed", "ranking": ["x"] * 3, "selected": []}, relevant) == ["not_retrieved"]
    low = {"status": "completed", "ranking": [f"x{i}" for i in range(15)] + ["d1"], "selected": ["x0"], "selected_units": 1}
    assert classify_retrieval(low, relevant) == ["ranked_too_low", "dropped_by_selection"]
    drift = {"status": "completed", "ranking": ["x"], "selected": [], "rewrite": {"validation": {"used": "rewrite"}}}
    assert classify_retrieval(drift, relevant, baseline={}, baseline_relevant_found=True) == ["rewrite_drift", "not_retrieved"]
    assert classify_retrieval({"status": "completed", "ranking": ["d1"], "selected": ["d1"], "selected_units": 1}, relevant) == []
    starved = {"status": "completed", "ranking": [], "target": ["a"], "units_ranked": 0, "cutoff": 2,
               "stage_status": {"metadata_postfiltering": "completed"}}  # fmt: skip
    assert classify_fixture(starved) == ["not_retrieved", "candidate_starvation"]  # an eligible target was never retrieved: the earlier stage


def test_answer_metrics_are_not_applicable_without_annotations(tmp_path):
    run = tmp_path / "run"
    raw = run / "raw" / "generation" / "cases"
    raw.mkdir(parents=True)
    (raw / "GEN_m__-.jsonl").write_text(json.dumps({"qid": "scifact:1", "dataset": "scifact", "status": "completed", "outcome": "answered",
                                                    "raw_answer": "Yes [E1] and [E9].", "prompt_labels": ["E1"], "generation_ms": 10}) + "\n")  # fmt: skip
    status = {"generation/cases/GEN_m__-": {"status": "COMPLETED", "model_identity": {"name": "m"}}}
    annotations = tmp_path / "a.jsonl"
    annotations.write_text(json.dumps({"case_id": "scifact:1", "annotation_status": "pending"}) + "\n")
    rows, failures, _ = generation_tables(run, status, annotations)
    overall = next(r for r in rows if r["group"] == "ALL")
    assert overall["annotated_cases"] == 0 and overall["correctness"] == "N/A" and overall["invalid_markers_total"] == 1
    assert failures[0]["primary"] == "invalid_citation"
    (run / "status.json").write_text(json.dumps(status))
    write_reports(run)
    assert "N/A" in (run / "summary.md").read_text() and (run / "generation_comparison.csv").exists()


@pytest.mark.parametrize("name", ["offline.yaml", "online.yaml", "generation.yaml"])
def test_every_configured_preset_exists_and_validates(name):
    config = load_yaml(name)
    for e in config.get("experiments", []):
        if "preset" in e:
            preset_config(e["preset"])
    if "retrieval_preset" in config:
        preset_config(config["retrieval_preset"])
