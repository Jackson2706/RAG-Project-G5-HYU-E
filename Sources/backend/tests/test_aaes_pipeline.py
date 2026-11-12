"""AAES presets end to end on the synthetic sample index (mock Ollama, fake cross-encoder). Written by Claude Code."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.rag.applicability import ChunkCondition
from app.rag.aaes import UNKNOWN_CAVEAT
from app.rag.presets import PRESETS_BY_ID

AAES_PRESETS = ("A0_AAES", "A1_AAES_HARD_FILTER", "A3_AAES_ALWAYS_CLARIFY", "A4_QUESTION_ONLY_AMBIGUITY", "A6_AAES_NO_TEMPORAL")


class FakeCrossEncoder:
    def predict(self, pairs, **kw):
        return [float(len(set(q.lower().split()) & set(t.lower().split()))) for q, t in pairs]


@pytest.fixture
def api(db, ollama, settings, monkeypatch):
    monkeypatch.setattr("app.api.get_settings", lambda: settings)
    monkeypatch.setattr("app.rag.blocks.evidence.reranking.cross_encoder.load_cross_encoder", lambda device: FakeCrossEncoder())
    with TestClient(create_app(db=db, ollama=ollama)) as client:
        yield client


def _tag_everything(db, campus, status):
    """Pretend the sample index was tagged: every chunk applies only to `campus`, with this condition status."""
    db.chunks.update_many({}, {"$set": {"applicability": ChunkCondition(campus=[campus]).to_dict(), "condition_status": status}})
    manifest = db.get_manifest()
    db.save_manifest({**manifest, "applicability": {"vocabulary_version": "v1"}})


def test_aaes_presets_are_listed_with_their_group(api):
    presets = {p["id"]: p for p in api.get("/api/pipeline/presets").json()["presets"]}
    for preset_id in AAES_PRESETS:
        assert presets[preset_id]["enabled"] and presets[preset_id]["errors"] == []
        assert presets[preset_id]["group"] in ("Ours (AAES)", "Ablations") and presets[preset_id]["description"]


def test_aaes_needs_a_tagged_index(api, corpus):
    api.post("/api/ingest", json={"folder": "raw"})
    res = api.post("/api/chat", json={"question": "How do I register for courses?", "stages": PRESETS_BY_ID["A0_AAES"]["stages"]})
    assert res.status_code == 422 and "applicability tags" in res.json()["detail"]["errors"][0]["message"]


def test_a0_answers_with_the_unknown_caveat_and_traces_every_step(api, corpus, db, fake_ollama):
    api.post("/api/ingest", json={"folder": "raw"})
    _tag_everything(db, "seoul", "unknown")
    body = {"question": "What documents does the need-based scholarship require?", "history": ["I'm a Seoul campus student."],
            "stages": PRESETS_BY_ID["A0_AAES"]["stages"]}  # fmt: skip
    trace = api.post("/api/chat", json=body).json()
    assert trace["status"] == "completed", trace["error"]
    assert trace["action"] == "ANSWER" and trace["unknown_condition_evidence"] is True
    assert trace["answer"].endswith(UNKNOWN_CAVEAT)
    stages = {s["stage_id"]: s for s in trace["stages"]}
    assert stages["query_understanding"]["output"]["profile"]["campus"]["status"] == "remembered"
    assert set(stages["reranking"]["details"]["labels"].values()) == {"unknown"}
    assert stages["evidence_sufficiency"]["output"]["action"] == "ANSWER"


def test_a0_abstains_without_the_llm_when_nothing_applies(api, corpus, db, fake_ollama):
    api.post("/api/ingest", json={"folder": "raw"})
    _tag_everything(db, "erica", "unconditioned")
    before = len(fake_ollama.requests)
    body = {"question": "I'm a Seoul campus student. What documents does the need-based scholarship require?",
            "stages": PRESETS_BY_ID["A0_AAES"]["stages"]}  # fmt: skip
    trace = api.post("/api/chat", json=body).json()
    assert trace["action"] == "ABSTAIN" and trace["outcome"] == "abstain" and "Seoul campus OIA office" in trace["answer"]
    assert len(fake_ollama.requests) == before


def test_a4_asks_about_a_word_in_the_question_without_the_llm(api, corpus, db, fake_ollama):
    api.post("/api/ingest", json={"folder": "raw"})
    _tag_everything(db, "seoul", "unconditioned")
    before = len(fake_ollama.requests)
    body = {"question": "I'm a Seoul campus student. Which scholarship documents do I need for my visa?",
            "stages": PRESETS_BY_ID["A4_QUESTION_ONLY_AMBIGUITY"]["stages"]}  # fmt: skip
    trace = api.post("/api/chat", json=body).json()
    assert trace["action"] == "CLARIFY", trace.get("error")
    stages = {s["stage_id"]: s for s in trace["stages"]}
    assert stages["evidence_sufficiency"]["output"]["signals"]["clarify_attribute"] == "visa"
    assert len(fake_ollama.requests) == before
