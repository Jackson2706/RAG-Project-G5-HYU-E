from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def api(app_state):
    with TestClient(create_app(app_state)) as client:
        yield client


def parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n") if not line.startswith(":"))
        if "event" in lines:
            events.append({"event": lines["event"], **json.loads(lines["data"])})
    return events


def test_health_and_registry(api, ingested):
    health = api.get("/api/v1/health").json()
    assert health["mongodb"]["ok"] and health["qdrant"]["ok"] and health["ollama"]["ok"]
    assert health["active_index"]["revision_id"] == ingested.revision_id
    registry = api.get("/api/v1/pipeline/registry").json()
    assert len(registry["stages"]) == 21


def test_config_reflects_active_index(api, ingested):
    body = api.get("/api/v1/pipeline/config").json()
    assert body["active_index_config"]["chunking"]["params"]["chunk_size"] == body["config"]["stages"]["chunking"]["params"]["chunk_size"]


def test_validate_returns_errors_and_snapshot(api):
    bad = api.post("/api/v1/pipeline/config/validate", json={"stages": {"reranking": {"enabled": True, "method": "cross_encoder"}}}).json()
    assert not bad["valid"] and bad["errors"][0]["stage_id"] == "reranking"
    good = api.post("/api/v1/pipeline/config/validate", json={"stages": {}}).json()
    assert good["valid"] and good["resolved"]["config_hash"]


def test_presets_save_and_list(api):
    created = api.post("/api/v1/pipeline/presets", json={"name": "My Hybrid", "config": {"stages": {"lexical_retrieval": {"enabled": True}, "hybrid_fusion": {"method": "rrf"}}}})
    assert created.status_code == 201 and created.json()["preset_id"] == "user_my_hybrid"
    presets = {p["preset_id"]: p for p in api.get("/api/v1/pipeline/presets").json()}
    assert presets["user_my_hybrid"]["available"] and not presets["advanced"]["available"]
    assert api.post("/api/v1/pipeline/presets", json={"name": "x", "config": {"stages": {"generation": {"enabled": False}}}}).status_code == 422


def test_chat_and_trace_lookup(api, ingested):
    res = api.post("/api/v1/chat", json={"question": "What should I bring to orientation?", "session_id": "abc"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["outcome"] == "answered"
    trace = api.get(f"/api/v1/traces/{body['request_id']}").json()
    assert trace["request_id"] == body["request_id"] and trace["session_id"] == "abc"
    assert api.get("/api/v1/traces/doesnotexist").status_code == 404


def test_chat_rejects_planned_method_before_running(api, fake_ollama):
    res = api.post("/api/v1/chat/stream", json={"question": "hi", "config": {"stages": {"query_rewriting": {"enabled": True}}}})
    assert res.status_code == 422 and not fake_ollama.requests


def test_chat_stream_event_sequence(api, ingested):
    with api.stream("POST", "/api/v1/chat/stream", json={"question": "How do I register for courses?"}) as res:
        assert res.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(res.read().decode())
    types = [e["event"] for e in events]
    assert types[0] == "pipeline_started" and types[-1] == "pipeline_completed"
    stage_events = [e for e in events if e["event"].startswith("stage_")]
    started = [e["stage"]["stage_id"] for e in stage_events if e["event"] == "stage_started"]
    assert started[0] == "query_understanding" and "generation" in started
    request_ids = {e["request_id"] for e in events}
    assert len(request_ids) == 1
    final = events[-1]["trace"]
    assert final["status"] == "completed" and len(final["stages"]) == 15


def test_documents_endpoints(api, ingested):
    docs = api.get("/api/v1/documents").json()["documents"]
    assert len(docs) == 5 and "content" not in docs[0]
    detail = api.get(f"/api/v1/documents/{docs[0]['doc_id']}").json()
    assert detail["chunks"] and detail["chunks"][0]["doc_id"] == docs[0]["doc_id"]
    assert api.get("/api/v1/documents/unknown").status_code == 404


def test_ingest_endpoints_validate_paths_and_types(api, settings):
    assert api.post("/api/v1/ingest/local", json={"path": "../../etc"}).status_code == 400
    bad = api.post("/api/v1/ingest/files", files={"files": ("evil.exe", b"MZ", "application/octet-stream")}, data={"ingest": "false"})
    assert bad.status_code == 415
    ok = api.post("/api/v1/ingest/files", files={"files": ("../note.md", b"# Note\n\nSynthetic upload.", "text/markdown")}, data={"ingest": "true"})
    assert ok.status_code == 200 and ok.json()["saved"] == ["raw/uploads/note.md"]
    assert ok.json()["ingestion"]["status"] == "completed"
    assert (settings.raw_dir / "uploads" / "note.md").exists()
