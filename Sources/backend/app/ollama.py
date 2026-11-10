"""A small async client for the local Ollama server (GET /api/tags, POST /api/show, POST /api/chat).

One client is shared by the app and by the benchmark runner, for generation and for the auxiliary LLM
calls (query rewriting, multi-query, HyDE, RankGPT).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url
        self.http = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(timeout, connect=5.0), transport=transport)

    async def list_models(self) -> list[dict]:
        """Installed models: [{"name", "parameter_size", "capabilities"}]."""
        try:
            response = await self.http.get("/api/tags")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Cannot reach Ollama at {self.base_url}. Is it running? ({exc.__class__.__name__})") from exc
        return [
            {"name": m["name"], "digest": m.get("digest"), "parameter_size": m.get("details", {}).get("parameter_size"),
             "quantization": m.get("details", {}).get("quantization_level"), "capabilities": m.get("capabilities", [])}
            for m in response.json().get("models", [])
        ]  # fmt: skip

    async def model_identity(self, model: dict) -> dict[str, Any]:
        """What exactly is this model: tag, digest, size, quantization, context length, capabilities (for experiment records)."""
        identity = {k: model.get(k) for k in ("name", "digest", "parameter_size", "quantization", "capabilities")}
        try:
            response = await self.http.post("/api/show", json={"model": model["name"]})
            response.raise_for_status()
            info = response.json()
            identity["family"] = info.get("details", {}).get("family")
            identity["context_length"] = next((v for k, v in info.get("model_info", {}).items() if k.endswith(".context_length")), None)
            identity["capabilities"] = info.get("capabilities", identity["capabilities"])
        except (httpx.HTTPError, ValueError):
            identity["show_error"] = "POST /api/show failed"
        return identity

    async def pick_model(self, requested: str, default: str) -> dict:
        """The requested installed model, else the default, else the first installed one."""
        models = await self.list_models()
        if not models:
            raise OllamaError("No Ollama models are installed. Run: ollama pull qwen3:4b")
        for name in (requested, default):
            if name:
                match = next((m for m in models if m["name"] == name), None)
                if match is None:
                    raise OllamaError(f"Model '{name}' is not installed. Installed: {', '.join(m['name'] for m in models)}")
                return match
        return models[0]

    async def chat_stream(self, model: dict, messages: list[dict], options: dict[str, Any], think: str = "off",
                          timeout: float | None = None, usage: dict | None = None) -> AsyncIterator[str]:
        """Yield the answer piece by piece.

        options: Ollama options, e.g. {"temperature": 0, "num_predict": 512, "num_ctx": 4096, "top_p": 0.9, "seed": 42}
        think:   "off" (ask a thinking model not to reason), "on" (allow it; the reasoning is returned by
                 Ollama separately and is NOT shown or stored), "model_default" (send nothing).
                 "on" with a model that cannot think is an error, never silently ignored.
        usage:   if given, filled with Ollama's token counts and timings when the answer is complete.
        "Thinking" models (e.g. qwen3) may still write private reasoning before a `</think>` tag even
        when asked not to. We hold text back until the tag appears and drop what came before.
        """
        thinking = "thinking" in model["capabilities"]
        body: dict[str, Any] = {"model": model["name"], "messages": messages, "stream": True, "options": options}
        if think == "on" and not thinking:
            raise OllamaError(f"Model '{model['name']}' does not support thinking; set Thinking to off.")
        if thinking and think != "model_default":
            body["think"] = think == "on"
        held: list[str] | None = [] if thinking and think == "off" else None
        try:
            request_timeout = httpx.Timeout(timeout, connect=5.0) if timeout else self.http.timeout
            async with self.http.stream("POST", "/api/chat", json=body, timeout=request_timeout) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise OllamaError(f"Ollama returned {response.status_code}: {response.text[:200]}")
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise OllamaError(f"Ollama error: {chunk['error']}")
                    text = chunk.get("message", {}).get("content", "")
                    if held is not None and text:
                        held.append(text)
                        joined = "".join(held)
                        if "</think>" not in joined:
                            continue
                        text, held = joined.split("</think>", 1)[1].lstrip(), None
                    if text:
                        yield text
                    if chunk.get("done"):
                        if usage is not None:
                            usage.update({k: chunk.get(k) for k in ("prompt_eval_count", "eval_count", "total_duration", "load_duration",
                                                                    "prompt_eval_duration", "eval_duration", "done_reason")})  # fmt: skip
                        if held:  # no closing reasoning tag was produced
                            text = "".join(held)
                            if "<think>" in text and chunk.get("done_reason") == "length":  # it was still reasoning
                                raise OllamaError("The model used all 'Max generated tokens' before answering. Increase the limit.")
                            yield text  # a normal answer (possibly cut at the limit: usage["done_reason"] == "length")
                        return
        except httpx.TimeoutException as exc:
            raise OllamaError("Ollama did not answer in time (timeout).") from exc
        except httpx.TransportError as exc:
            raise OllamaError(f"Lost connection to Ollama at {self.base_url}.") from exc

    async def complete(self, model: dict, messages: list[dict], options: dict[str, Any], think: str = "off",
                       timeout: float | None = None) -> tuple[str, dict]:
        """The whole answer at once (for auxiliary calls such as query rewriting): (text, usage)."""
        usage: dict = {}
        parts = [piece async for piece in self.chat_stream(model, messages, options, think, timeout, usage)]
        return "".join(parts).strip(), usage
