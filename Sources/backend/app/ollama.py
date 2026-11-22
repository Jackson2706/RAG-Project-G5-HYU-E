"""Local Ollama and cloud Groq chat client.

The existing OllamaClient name is kept as the internal interface used by the RAG pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx


class OllamaError(Exception):
    pass


# shortcut: HYU_LLM_CACHE=<dir> replays identical requests (same model digest, messages, options, think) from disk. Only the
# evaluation scripts set it; every call is temperature 0 with seed 42, so a replay equals a rerun. Off (None) in the app.
CACHE_DIR = Path(os.environ["HYU_LLM_CACHE"]) if os.environ.get("HYU_LLM_CACHE") else None
if CACHE_DIR:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_key(model: dict, messages: list[dict], options: dict, think: str) -> str:
    raw = json.dumps([model["name"], model.get("digest"), messages, options, think], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0, transport: httpx.AsyncBaseTransport | None = None,
                 api_key: str | None = None, provider: str = "ollama", default_model: str = "") -> None:
        self.base_url = base_url
        self.provider = provider
        self.default_model = default_model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self.http = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=httpx.Timeout(timeout, connect=5.0), transport=transport)

    @classmethod
    def from_settings(cls, settings) -> "OllamaClient":
        provider = (settings.llm_provider or "ollama").lower()
        if provider == "groq":
            return cls(settings.groq_base_url, settings.ollama_timeout, api_key=settings.groq_api_key,
                       provider="groq", default_model=settings.groq_chat_model)
        return cls(settings.ollama_base_url, settings.ollama_timeout,
                   provider="ollama", default_model=settings.ollama_chat_model)

    async def list_models(self) -> list[dict]:
        """Installed models: [{"name", "parameter_size", "capabilities"}]."""
        try:
            response = await self.http.get("/models" if self.provider == "groq" else "/api/tags")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            service = "Groq" if self.provider == "groq" else "Ollama"
            raise OllamaError(f"Cannot reach {service} at {self.base_url}. ({exc.__class__.__name__})") from exc
        if self.provider == "groq":
            return [
                {"name": item["id"], "digest": None, "parameter_size": None,
                 "quantization": None, "capabilities": ["completion"]}
                for item in response.json().get("data", [])
            ]
        return [
            {"name": m["name"], "digest": m.get("digest"), "parameter_size": m.get("details", {}).get("parameter_size"),
             "quantization": m.get("details", {}).get("quantization_level"), "capabilities": m.get("capabilities", [])}
            for m in response.json().get("models", [])
        ]  # fmt: skip

    async def model_identity(self, model: dict) -> dict[str, Any]:
        """What exactly is this model: tag, digest, size, quantization, context length, capabilities (for experiment records)."""
        identity = {k: model.get(k) for k in ("name", "digest", "parameter_size", "quantization", "capabilities")}
        if self.provider == "groq":
            identity["provider"] = "groq"
            identity["context_length"] = None
            return identity
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
            if self.provider == "groq":
                raise OllamaError("No Groq chat models are available.")
            raise OllamaError("No Ollama models are installed. Run: ollama pull qwen3:4b")
        if self.provider == "groq" and not default:
            default = self.default_model
        if self.provider == "groq" and not requested:
            requested = default
        for name in (requested, default):
            if name:
                match = next((m for m in models if m["name"] == name), None)
                if match is None:
                    if self.provider == "groq":
                        raise OllamaError(f"Groq model '{name}' is not available. Available: {', '.join(m['name'] for m in models)}")
                    raise OllamaError(f"Model '{name}' is not installed. Installed: {', '.join(m['name'] for m in models)}")
                return match
        return models[0]

    async def chat_stream(self, model: dict, messages: list[dict], options: dict[str, Any], think: str = "off",
                          timeout: float | None = None, usage: dict | None = None, _no_cache: bool = False) -> AsyncIterator[str]:
        if self.provider == "groq":
            async for piece in self._groq_chat_stream(model, messages, options, timeout, usage):
                yield piece
            return
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
        key = cache_key(model, messages, options, think) if CACHE_DIR and not _no_cache else None
        if key and (hit := CACHE_DIR / f"{key}.json").exists():  # an identical request was answered before (evaluation runs only)
            cached = json.loads(hit.read_text())
            if usage is not None:
                usage.update(cached["usage"], cache_hit=True)
            yield cached["text"]
            return
        if key:
            pieces: list[str] = []
            inner_usage: dict = {}
            async for piece in self.chat_stream(model, messages, options, think, timeout, inner_usage, _no_cache=True):
                pieces.append(piece)
                yield piece
            if usage is not None:
                usage.update(inner_usage)
            (CACHE_DIR / f"{key}.json").write_text(json.dumps({"text": "".join(pieces), "usage": inner_usage}))
            return
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

    async def _groq_chat_stream(self, model: dict, messages: list[dict], options: dict[str, Any],
                                timeout: float | None = None, usage: dict | None = None) -> AsyncIterator[str]:
        body: dict[str, Any] = {
            "model": model["name"],
            "messages": messages,
            "stream": True,
            "temperature": max(float(options.get("temperature", 0.2)), 1e-8),
            "top_p": float(options.get("top_p", 0.9)),
            "max_tokens": int(options.get("num_predict", 1024)),
        }
        if options.get("seed") is not None:
            body["seed"] = int(options["seed"])
        received_text = False
        try:
            request_timeout = httpx.Timeout(timeout, connect=5.0) if timeout else self.http.timeout
            async with self.http.stream("POST", "/chat/completions", json=body, timeout=request_timeout) as response:
                if response.status_code != 200:
                    await response.aread()
                    try:
                        detail = response.json().get("error", {}).get("message")
                    except Exception:
                        detail = None
                    raise OllamaError(f"Groq returned {response.status_code}: {detail or response.text[:200]}")
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if "error" in chunk:
                        raise OllamaError(f"Groq error: {chunk['error']}")
                    choice = (chunk.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    text = delta.get("content")
                    if text:
                        received_text = True
                        yield text
                    chunk_usage = chunk.get("x_groq", {}).get("usage") or chunk.get("usage")
                    if usage is not None and chunk_usage:
                        usage.update({
                            "prompt_tokens": chunk_usage.get("prompt_tokens"),
                            "completion_tokens": chunk_usage.get("completion_tokens"),
                            "total_tokens": chunk_usage.get("total_tokens"),
                            "done_reason": choice.get("finish_reason"),
                        })
            if not received_text:
                raise OllamaError("Groq returned no answer text. Check the Groq model, key, and chat-completions access.")
        except httpx.TimeoutException as exc:
            raise OllamaError("Groq did not answer in time (timeout).") from exc
        except httpx.TransportError as exc:
            raise OllamaError(f"Lost connection to Groq at {self.base_url}.") from exc

    async def complete(self, model: dict, messages: list[dict], options: dict[str, Any], think: str = "off",
                       timeout: float | None = None) -> tuple[str, dict]:
        """The whole answer at once (for auxiliary calls such as query rewriting): (text, usage)."""
        usage: dict = {}
        parts = [piece async for piece in self.chat_stream(model, messages, options, think, timeout, usage)]
        return "".join(parts).strip(), usage
