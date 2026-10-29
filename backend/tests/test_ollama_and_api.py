"""Tests for the Ollama client and the HTTP API."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.ollama import OllamaClient, OllamaError


@pytest.mark.anyio
async def test_ollama_lists_models_and_streams_answers(ollama, fake_ollama):
    assert [m["name"] for m in await ollama.list_models()] == ["test-model"]
    fake_ollama.answer = "Hello there"
    pieces = [p async for p in ollama.chat_stream(await ollama.pick_model("", ""), [], 0.1, 50)]
    assert "".join(pieces) == "Hello there"


@pytest.mark.anyio
async def test_ollama_errors_are_clear(ollama, fake_ollama):
    with pytest.raises(OllamaError, match="not installed"):
        await ollama.pick_model("imaginary-model", "")
    fake_ollama.models = []
    with pytest.raises(OllamaError, match="ollama pull"):
        await ollama.pick_model("", "")
    fake_ollama.fail = "connect"
    with pytest.raises(OllamaError, match="Cannot reach Ollama"):
        await ollama.list_models()


@pytest.mark.anyio
async def test_hidden_reasoning_of_thinking_models_is_removed(ollama, fake_ollama):
    fake_ollama.answer = "Let me think about [E9] first </think> The answer is 18 [E1]."
    pieces = [p async for p in ollama.chat_stream({"name": "qwen3:4b", "capabilities": ["thinking"]}, [], 0.1, 50)]
    assert "".join(pieces) == "The answer is 18 [E1]." and fake_ollama.requests[-1]["think"] is False


@pytest.mark.anyio
async def test_ollama_http_error():
    client = OllamaClient("http://x", transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"error": "boom"})))
    with pytest.raises(OllamaError, match="500"):
        [p async for p in client.chat_stream({"name": "m", "capabilities": []}, [], 0.1, 10)]


# ------------------------------------------------------------------ API


@pytest.fixture
def api(db, ollama, settings, monkeypatch):
    monkeypatch.setattr("app.api.get_settings", lambda: settings)
    with TestClient(create_app(db=db, ollama=ollama)) as client:
        yield client


def test_registry_endpoint(api):
    stages = {s["stage_id"]: s for s in api.get("/api/pipeline/registry").json()["stages"]}
    assert len(stages) == 19
    assert stages["dense_retrieval"]["implemented"] and stages["dense_retrieval"]["methods"][0]["parameters"]["top_k"]["default"] == 5
    assert stages["dense_retrieval"]["group"] == "Candidate Retrieval" and stages["dense_retrieval"]["folder"] == "app/rag/blocks/retrieval/dense_retrieval/"
    assert not stages["reranking"]["implemented"] and stages["reranking"]["base_class"] == "BaseReranker"
    for name in ("metadata_prefiltering", "metadata_postfiltering"):  # the two filtering placements, both planned
        assert stages[name]["optional"] and not stages[name]["implemented"]
    assert "citation_verification" not in stages and "response_guard" not in stages


def test_config_validation_endpoint(api):
    bad = api.post("/api/pipeline/config/validate", json={"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 500}}}).json()
    assert not bad["valid"] and bad["errors"][0] == {"stage_id": "dense_retrieval", "param": "top_k", "message": "Top K must be at most 20"}
    assert api.post("/api/pipeline/config/validate", json={}).json()["valid"]


def test_chat_rejects_planned_methods_before_running(api, fake_ollama):
    res = api.post("/api/chat", json={"question": "hi", "stages": {"reranking": {"method": "cross_encoder"}}})
    assert res.status_code == 422 and "not implemented" in res.json()["detail"]["errors"][0]["message"]
    assert fake_ollama.requests == []


def test_ingest_then_stream_a_question(api, corpus):
    report = api.post("/api/ingest", json={"folder": "raw"}).json()
    assert report["documents"] == 5
    assert api.post("/api/ingest", json={"folder": "../../etc"}).status_code == 400
    with api.stream("POST", "/api/chat/stream", json={"question": "How do I register for courses?"}) as res:
        events = [json.loads(line[6:]) for line in res.read().decode().split("\n\n") if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[0] == "started" and types[-1] == "done" and "answer_delta" in types
    final = events[-1]["trace"]
    assert final["status"] == "completed" and len({e["request_id"] for e in events}) == 1
    assert api.get(f"/api/traces/{final['request_id']}").json()["answer"] == final["answer"]
    assert api.get("/api/traces/unknown").status_code == 404


def test_health_and_documents(api, ingested):
    health = api.get("/api/health").json()
    assert health["mongodb"]["ok"] and health["qdrant"]["ok"] and health["ollama"]["ok"] and health["index"]["documents"] == 5
    docs = api.get("/api/documents").json()["documents"]
    assert len(docs) == 5 and {"doc_id", "title", "source_uri", "language", "source_hash", "metadata"} <= set(docs[0])
