"""G1 (oracle evidence) and A2 (oracle profile) with a dev demo case (P8D T37, A33). Written by Claude Code."""

from __future__ import annotations

import json

import pytest

from app.demo import load_demo_cases
from app.rag.presets import PRESETS_BY_ID
from tests.test_aaes_pipeline import _tag_everything, api  # noqa: F401  (fixture)

DOC = {"doc_id": "D1", "text": "Seoul students submit the scholarship form by March 3.", "title": "Scholarship", "source_uri": "https://x/1"}
CASE = {"case_id": "T14-900", "split": "dev", "slice": "conditional", "snapshot_id": "s", "question": "When is the scholarship form due?",
        "session_history": [{"role": "user", "text": "Hi."}], "stated_profile": {"campus": "seoul"}, "expected_behavior": "answer",
        "gold_evidence": [{"doc_id": "D1", "char_start": 0, "char_end": 54}]}


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr("app.api.load_demo_cases", lambda: [CASE])
    monkeypatch.setattr("app.demo._documents", lambda snapshot_id: {"D1": DOC})


def test_oracle_presets_are_listed_and_need_a_demo_case(api, corpus):  # noqa: F811
    presets = {p["id"]: p for p in api.get("/api/pipeline/presets").json()["presets"]}
    for preset_id, group in (("G1_ORACLE_CONTEXT", "Brackets"), ("A2_AAES_ORACLE_PROFILE", "Ablations")):
        assert presets[preset_id]["enabled"] and presets[preset_id]["needs_demo_case"] and presets[preset_id]["group"] == group
    assert presets["A0_AAES"]["needs_demo_case"] is False
    api.post("/api/ingest", json={"folder": "raw"})
    res = api.post("/api/chat", json={"question": "When is it due?", "stages": PRESETS_BY_ID["G1_ORACLE_CONTEXT"]["stages"]})
    assert res.status_code == 422 and "needs a labeled demo case" in res.json()["detail"]["errors"][0]["message"]


def test_demo_cases_endpoint_is_empty_with_a_reason_before_the_freeze(api, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr("app.demo.DEMO_PATH", tmp_path / "missing.jsonl")
    assert api.get("/api/demo/cases").json() == {"cases": [], "reason": "no demo cases yet (they come from the frozen dev split)"}


def test_a_test_case_is_never_a_demo_case(tmp_path):
    path = tmp_path / "demo.jsonl"
    path.write_text(json.dumps({**CASE, "split": "test"}) + "\n")
    with pytest.raises(ValueError, match="not from the dev split"):
        load_demo_cases(path)


def test_g1_answers_from_the_gold_span(api, corpus, demo, fake_ollama):  # noqa: F811
    assert api.get("/api/demo/cases").json()["cases"][0]["history"] == ["Hi."]
    api.post("/api/ingest", json={"folder": "raw"})
    body = {"question": CASE["question"], "demo_case_id": "T14-900", "stages": PRESETS_BY_ID["G1_ORACLE_CONTEXT"]["stages"]}
    trace = api.post("/api/chat", json=body).json()
    assert trace["status"] == "completed", trace["error"]
    stages = {s["stage_id"]: s for s in trace["stages"]}
    assert [e["chunk_id"] for e in stages["evidence_selection"]["output"]] == ["gold:D1:0-54"]
    assert trace["sources"] and trace["sources"][0]["chunk_id"] == "gold:D1:0-54"


def test_a2_reads_the_labeled_profile(api, corpus, db, demo, fake_ollama):  # noqa: F811
    api.post("/api/ingest", json={"folder": "raw"})
    _tag_everything(db, "seoul", "unconditioned")
    body = {"question": "When is the scholarship form due?", "demo_case_id": "T14-900", "stages": PRESETS_BY_ID["A2_AAES_ORACLE_PROFILE"]["stages"]}
    trace = api.post("/api/chat", json=body).json()
    assert trace["status"] == "completed", trace["error"]
    profile = {s["stage_id"]: s for s in trace["stages"]}["query_understanding"]["output"]["profile"]
    assert profile["campus"] == {"values": ["seoul"], "status": "stated", "evidence": "labeled case"}
    assert profile["visa"]["status"] == "missing"
    assert api.post("/api/chat", json={**body, "demo_case_id": "nope"}).status_code == 422
