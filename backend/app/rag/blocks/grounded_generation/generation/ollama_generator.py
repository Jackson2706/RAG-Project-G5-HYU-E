"""IMPLEMENTED — a local Ollama chat model, streamed."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.rag.blocks.grounded_generation.generation.base import BaseGenerator
from app.rag.schemas import GenerationResult, PromptContext


class OllamaGenerator(BaseGenerator):
    """Hyperparameters: model, temperature, max_tokens."""

    async def generate(self, prompt: PromptContext, on_token: Callable[[str], None]) -> GenerationResult:
        ollama, settings = self.services.ollama, self.services.settings
        model = await ollama.pick_model(self.params["model"], settings.ollama_chat_model)
        start, first_token_ms, parts = time.perf_counter(), None, []
        async for piece in ollama.chat_stream(model, prompt.messages, self.params["temperature"], self.params["max_tokens"]):
            if first_token_ms is None:
                first_token_ms = round((time.perf_counter() - start) * 1000, 1)
            parts.append(piece)
            on_token(piece)
        return GenerationResult(answer="".join(parts).strip(), model=model["name"], first_token_ms=first_token_ms)
