from __future__ import annotations

import httpx
import pytest

from app.services.ollama import OllamaClient, OllamaError, model_options
from tests.conftest import FakeOllama

pytestmark = pytest.mark.anyio


def client(fake: FakeOllama) -> OllamaClient:
    return OllamaClient("http://ollama.test", timeout=5, transport=httpx.MockTransport(fake.handler))


async def test_status_models_and_show():
    fake = FakeOllama()
    c = client(fake)
    assert await c.version() == "test"
    models = await c.list_models()
    assert models[0]["name"] == "test-model:1b" and models[0]["parameter_size"] == "1B"
    info = await c.show("test-model:1b")
    assert info["context_length"] == 4096 and info["capabilities"] == ["completion"]


async def test_resolve_model_never_invents_names():
    fake = FakeOllama()
    c = client(fake)
    assert await c.resolve_model("", "") == "test-model:1b"
    with pytest.raises(OllamaError) as err:
        await c.resolve_model("llama-imaginary", "")
    assert err.value.kind == "model_not_found"
    fake.models = []
    with pytest.raises(OllamaError) as err:
        await c.resolve_model("", "")
    assert err.value.kind == "no_model" and "ollama pull" in str(err.value)


async def test_chat_stream_yields_content_only_and_final_stats():
    fake = FakeOllama()
    fake.answer = "Hello world"
    events = [e async for e in client(fake).chat_stream("test-model:1b", [{"role": "user", "content": "hi"}], {"temperature": 0})]
    assert "".join(e.get("delta", "") for e in events) == "Hello world"
    assert events[-1]["done"] and events[-1]["eval_count"] == 2
    assert fake.requests[0]["options"] == {"temperature": 0} and fake.requests[0]["stream"] is True


async def test_connection_and_http_errors():
    fake = FakeOllama()
    fake.fail = "connect"
    with pytest.raises(OllamaError) as err:
        await client(fake).list_models()
    assert err.value.kind == "connection" and "ollama serve" in str(err.value)
    fake.fail = "500"
    with pytest.raises(OllamaError) as err:
        [e async for e in client(fake).chat_stream("test-model:1b", [], {})]
    assert err.value.kind == "http" and "boom" in str(err.value)


async def test_timeout_is_reported():
    def slow(request):
        raise httpx.ReadTimeout("timed out", request=request)

    c = OllamaClient("http://ollama.test", transport=httpx.MockTransport(slow))
    with pytest.raises(OllamaError) as err:
        [e async for e in c.chat_stream("m", [], {}, timeout=1)]
    assert err.value.kind == "timeout"


async def test_stream_without_done_is_an_error():
    def truncated(request):
        return httpx.Response(200, content=b'{"message": {"content": "partial"}, "done": false}\n')

    c = OllamaClient("http://ollama.test", transport=httpx.MockTransport(truncated))
    with pytest.raises(OllamaError) as err:
        [e async for e in c.chat_stream("m", [], {})]
    assert err.value.kind == "stream"


def test_only_supported_options_are_sent():
    params = {"temperature": 0.2, "seed": None, "stop": [], "stream": True, "timeout_s": 30, "model": "x", "num_ctx": 4096, "top_k": 40}
    assert model_options(params) == {"temperature": 0.2, "num_ctx": 4096, "top_k": 40}


async def test_reasoning_in_content_is_removed_for_thinking_models():
    fake = FakeOllama()
    fake.answer = "Let me think about [S9] sources </think> The answer is 18 [S1]."
    events = [e async for e in client(fake).chat_stream("test-model:1b", [], {}, strip_reasoning=True)]
    text = "".join(e.get("delta", "") for e in events)
    assert text == "The answer is 18 [S1]." and "[S9]" not in text
    assert events[-1]["reasoning_chars_removed"] > 0


async def test_thinking_model_answering_directly_is_kept():
    fake = FakeOllama()
    fake.answer = "Direct answer [S1]."
    events = [e async for e in client(fake).chat_stream("test-model:1b", [], {}, strip_reasoning=True)]
    assert "".join(e.get("delta", "") for e in events) == "Direct answer [S1]."


async def test_reasoning_that_exhausts_the_budget_is_an_error():
    def handler(request):
        lines = [b'{"message": {"content": "thinking forever"}, "done": false}', b'{"message": {"content": ""}, "done": true, "done_reason": "length"}']
        return httpx.Response(200, content=b"\n".join(lines))

    c = OllamaClient("http://ollama.test", transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaError, match="num_predict"):
        [e async for e in c.chat_stream("m", [], {}, strip_reasoning=True)]
