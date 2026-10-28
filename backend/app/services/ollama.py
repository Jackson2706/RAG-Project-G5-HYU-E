"""Async client for the native Ollama HTTP API (/api/tags, /api/show, /api/chat, /api/version)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx

# Model options accepted by Ollama's `options` object that the registry exposes.
REASONING_END = "</think>"
OLLAMA_OPTIONS = {"temperature", "top_p", "top_k", "min_p", "num_ctx", "num_predict", "seed", "repeat_penalty", "stop"}


class OllamaError(Exception):
    def __init__(self, kind: Literal["connection", "timeout", "model_not_found", "no_model", "http", "stream"], message: str):
        super().__init__(message)
        self.kind = kind


def model_options(params: dict[str, Any]) -> dict[str, Any]:
    """Keep only Ollama model options; drop unset values (None / empty stop list)."""
    return {k: v for k, v in params.items() if k in OLLAMA_OPTIONS and v is not None and v != []}


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(timeout, connect=5.0), transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kw: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kw)
        except httpx.TimeoutException as exc:
            raise OllamaError("timeout", f"Ollama request {path} timed out") from exc
        except httpx.TransportError as exc:
            raise OllamaError("connection", f"Cannot reach Ollama at {self.base_url} ({exc.__class__.__name__}). Is `ollama serve` running?") from exc
        if response.status_code == 404:
            raise OllamaError("model_not_found", _error_text(response) or f"{path} returned 404")
        if response.status_code >= 400:
            raise OllamaError("http", f"Ollama {path} returned {response.status_code}: {_error_text(response)}")
        return response.json()

    async def version(self) -> str:
        return (await self._request("GET", "/api/version")).get("version", "unknown")

    async def list_models(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/tags")
        return [
            {"name": m["name"], "size": m.get("size"), "modified_at": m.get("modified_at"),
             "family": m.get("details", {}).get("family"), "parameter_size": m.get("details", {}).get("parameter_size"),
             "quantization": m.get("details", {}).get("quantization_level")}
            for m in data.get("models", [])
        ]  # fmt: skip

    async def show(self, model: str) -> dict[str, Any]:
        data = await self._request("POST", "/api/show", json={"model": model})
        info = data.get("model_info", {}) or {}
        context_length = next((v for k, v in info.items() if k.endswith(".context_length")), None)
        return {"model": model, "capabilities": data.get("capabilities", []), "details": data.get("details", {}),
                "context_length": context_length, "parameters": data.get("parameters", "")}  # fmt: skip

    async def resolve_model(self, requested: str, fallback: str) -> str:
        """Pick `requested`, else `fallback` (env), else the first installed model — always an installed one."""
        installed = [m["name"] for m in await self.list_models()]
        if not installed:
            raise OllamaError("no_model", "No Ollama models are installed. Run `ollama pull <model>` (e.g. `ollama pull qwen3:4b`).")
        for name in (requested, fallback):
            if name:
                if name in installed:
                    return name
                raise OllamaError("model_not_found", f"Model '{name}' is not installed. Installed: {', '.join(installed)}")
        return installed[0]

    async def chat_stream(
        self, model: str, messages: list[dict[str, str]], options: dict[str, Any], think: bool | None = None,
        timeout: float | None = None, strip_reasoning: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields {'delta': str} for each content chunk and finally {'done': True, ...stats}.

        Private reasoning is never forwarded: `message.thinking` is ignored, and with
        `strip_reasoning` (thinking-capable models) content is held back until a closing
        `</think>` tag, and everything up to that tag is dropped. Some models emit their
        reasoning inside `content` even when `think` is false.
        """
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": True, "options": options}
        if think is not None:
            body["think"] = think
        t = httpx.Timeout(timeout or self.timeout, connect=5.0)
        held: list[str] | None = [] if strip_reasoning else None
        removed = 0
        try:
            async with self._client.stream("POST", "/api/chat", json=body, timeout=t) as response:
                if response.status_code >= 400:
                    await response.aread()
                    kind = "model_not_found" if response.status_code == 404 else "http"
                    raise OllamaError(kind, f"Ollama /api/chat returned {response.status_code}: {_error_text(response)}")
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        raise OllamaError("stream", f"Ollama stream error: {chunk['error']}")
                    content = chunk.get("message", {}).get("content", "")
                    if content and held is not None:
                        held.append(content)
                        buffered = "".join(held)
                        if REASONING_END in buffered:
                            reasoning, content = buffered.split(REASONING_END, 1)
                            removed, held = len(reasoning) + len(REASONING_END), None
                            content = content.lstrip()
                        else:
                            content = ""
                    if content:
                        yield {"delta": content}
                    if chunk.get("done"):
                        if held:
                            if chunk.get("done_reason") == "length":
                                raise OllamaError("stream", "The model's reasoning used the whole output budget before it answered; "
                                                            "increase 'Max output tokens' (num_predict).")  # fmt: skip
                            yield {"delta": "".join(held)}  # no reasoning block: the model answered directly
                        yield {"done": True, "done_reason": chunk.get("done_reason"), "prompt_eval_count": chunk.get("prompt_eval_count"),
                               "eval_count": chunk.get("eval_count"), "total_duration_ms": (chunk.get("total_duration") or 0) / 1e6,
                               "reasoning_chars_removed": removed}  # fmt: skip
                        return
                raise OllamaError("stream", "Ollama stream ended without a final 'done' message")
        except httpx.TimeoutException as exc:
            raise OllamaError("timeout", f"Generation exceeded the {t.read:.0f}s timeout") from exc
        except httpx.TransportError as exc:
            raise OllamaError("connection", f"Lost connection to Ollama during generation ({exc.__class__.__name__})") from exc


def _error_text(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", response.text))
    except (ValueError, json.JSONDecodeError):
        return response.text[:300]
