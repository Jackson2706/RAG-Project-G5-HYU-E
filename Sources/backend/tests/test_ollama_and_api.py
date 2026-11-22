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
    usage = {}
    pieces = [p async for p in ollama.chat_stream(await ollama.pick_model("", ""), [], {"temperature": 0.1, "num_predict": 50}, usage=usage)]
    assert "".join(pieces) == "Hello there" and usage["done_reason"] == "stop"
    assert fake_ollama.requests[-1]["options"] == {"temperature": 0.1, "num_predict": 50}


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
    pieces = [p async for p in ollama.chat_stream({"name": "qwen3:4b", "capabilities": ["thinking"]}, [], {"num_predict": 50})]
    assert "".join(pieces) == "The answer is 18 [E1]." and fake_ollama.requests[-1]["think"] is False


@pytest.mark.anyio
async def test_a_cut_off_answer_is_returned_but_unfinished_reasoning_is_an_error(ollama, fake_ollama):
    qwen = {"name": "qwen3.5:4b", "capabilities": ["thinking"]}
    fake_ollama.answer, fake_ollama.done_reason = "a long rewritten search query that hit the", "length"
    usage = {}
    pieces = [p async for p in ollama.chat_stream(qwen, [], {"num_predict": 8}, usage=usage)]
    assert "".join(pieces) == fake_ollama.answer and usage["done_reason"] == "length"
    fake_ollama.answer = "<think> still reasoning about"
    with pytest.raises(OllamaError, match="Max generated tokens"):
        [p async for p in ollama.chat_stream(qwen, [], {"num_predict": 8})]


@pytest.mark.anyio
async def test_thinking_on_for_a_model_that_cannot_think_is_an_error(ollama, fake_ollama):
    with pytest.raises(OllamaError, match="does not support thinking"):
        [p async for p in ollama.chat_stream({"name": "llama2:7b", "capabilities": ["completion"]}, [], {}, think="on")]
    assert fake_ollama.requests == []


@pytest.mark.anyio
async def test_ollama_http_error():
    client = OllamaClient("http://x", transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"error": "boom"})))
    with pytest.raises(OllamaError, match="500"):
        [p async for p in client.chat_stream({"name": "m", "capabilities": []}, [], {"num_predict": 10})]


@pytest.mark.anyio
async def test_groq_uses_openai_compatible_models_and_streaming():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "qwen/qwen3.8-27b"}]})
        if request.url.path.endswith("/chat/completions"):
            body = json.loads(request.content)
            assert body["model"] == "qwen/qwen3.8-27b"
            assert body["stream"] is True
            content = [
                'data: {"choices":[{"delta":{"content":"Groq "},"finish_reason":null}]}\n\n',
                'data: {"choices":[{"delta":{"content":"works"},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}\n\n',
                "data: [DONE]\n\n",
            ]
            return httpx.Response(200, text="".join(content), headers={"content-type": "text/event-stream"})
        return httpx.Response(404)

    client = OllamaClient(
        "https://api.groq.com/openai/v1",
        api_key="test-key",
        provider="groq",
        default_model="qwen/qwen3.8-27b",
        transport=httpx.MockTransport(handler),
    )
    model = await client.pick_model("", "")
    usage = {}
    pieces = [p async for p in client.chat_stream(model, [], {"temperature": 0.1, "top_p": 0.9, "num_predict": 100}, usage=usage)]
    assert "".join(pieces) == "Groq works"
    assert usage["total_tokens"] == 12


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
    assert stages["reranking"]["implemented"] and stages["reranking"]["base_class"] == "BaseReranker"
    for name in ("metadata_prefiltering", "metadata_postfiltering"):  # the two filtering placements, both optional
        assert stages[name]["optional"] and stages[name]["implemented"] and stages[name]["default_method"] is None
    assert not next(m for m in stages["chunking"]["methods"] if m["method_id"] == "semantic")["implemented"]
    assert stages["dense_retrieval"]["methods"][0]["parameters"]["search_mode"]["advanced"]
    assert "citation_verification" not in stages and "response_guard" not in stages


def test_azure_static_web_app_cors(api):
    for origin in (
        "https://calm-ground-0036c6b00.4.azurestaticapps.net",
        "https://preview-123.azurestaticapps.net",
    ):
        response = api.options(
            "/api/pipeline/registry",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_config_validation_endpoint(api):
    bad = api.post("/api/pipeline/config/validate", json={"dense_retrieval": {"method": "qdrant_cosine", "params": {"top_k": 5000}}}).json()
    assert not bad["valid"] and bad["errors"][0] == {"stage_id": "dense_retrieval", "param": "top_k", "message": "Top K must be at most 1000"}
    assert api.post("/api/pipeline/config/validate", json={}).json()["valid"]


def test_chat_rejects_planned_methods_before_running(api, fake_ollama):
    res = api.post("/api/chat", json={"question": "hi", "stages": {"reranking": {"method": "metadata_aware"}}})
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


def test_llm_cache_replays_an_identical_request(tmp_path, monkeypatch):
    """HYU_LLM_CACHE: the second identical request is served from disk, a different one is not."""
    import asyncio

    import httpx

    from app import ollama as mod

    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, text='{"message": {"content": "hi"}, "done": true, "eval_count": 1}\n')

    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    client = mod.OllamaClient("http://x", transport=httpx.MockTransport(handler))
    model = {"name": "m", "digest": "d", "capabilities": []}
    run = lambda content: asyncio.run(client.complete(model, [{"role": "user", "content": content}], {"temperature": 0}))  # noqa: E731
    assert run("q")[0] == "hi" and run("q")[0] == "hi" and len(calls) == 1
    assert run("other")[0] == "hi" and len(calls) == 2
