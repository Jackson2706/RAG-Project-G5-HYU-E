"""A small async client for the local Ollama server (GET /api/tags, POST /api/chat)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

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
            {"name": m["name"], "parameter_size": m.get("details", {}).get("parameter_size"), "capabilities": m.get("capabilities", [])}
            for m in response.json().get("models", [])
        ]

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

    async def chat_stream(self, model: dict, messages: list[dict], temperature: float, max_tokens: int) -> AsyncIterator[str]:
        """Yield the answer piece by piece.

        "Thinking" models (e.g. qwen3) may write private reasoning before a `</think>` tag even
        when asked not to. We hold text back until the tag appears and drop what came before.
        """
        thinking = "thinking" in model["capabilities"]
        body = {"model": model["name"], "messages": messages, "stream": True, "options": {"temperature": temperature, "num_predict": max_tokens}}
        if thinking:
            body["think"] = False
        held: list[str] | None = [] if thinking else None
        try:
            async with self.http.stream("POST", "/api/chat", json=body) as response:
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
                        if held:  # no reasoning tag was produced
                            if chunk.get("done_reason") == "length":
                                raise OllamaError("The model used all 'Max generated tokens' before answering. Increase the limit.")
                            yield "".join(held)
                        return
        except httpx.TimeoutException as exc:
            raise OllamaError("Ollama did not answer in time (timeout).") from exc
        except httpx.TransportError as exc:
            raise OllamaError(f"Lost connection to Ollama at {self.base_url}.") from exc
