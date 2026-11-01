"""IMPLEMENTED — a local Ollama chat model, streamed."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.rag.blocks.grounded_generation.generation.base import BaseGenerator
from app.rag.schemas import GenerationResult, PromptContext

PROMPT_TOKEN_MARGIN = 1.25  # the prompt is measured with the embedding tokenizer; LLM tokenizers count differently


class OllamaGenerator(BaseGenerator):
    """Hyperparameters: model, temperature, top_p, top_k, context_window (num_ctx), max_tokens (num_predict),
    seed (-1 = random), thinking (off / on / model_default), timeout_s.

    Context budget: the prompt (estimated) plus max_tokens must fit `context_window`. For a fair
    backbone comparison use the SAME context_window for every model (e.g. 4096, Llama 2's limit),
    so no model receives more evidence than another. A prompt that does not fit is an error, never
    silently cut.
    """

    async def generate(self, prompt: PromptContext, on_token: Callable[[str], None]) -> GenerationResult:
        ollama, settings, p = self.services.ollama, self.services.settings, self.params
        model = await ollama.pick_model(p["model"], settings.ollama_chat_model)
        estimated = round(sum(self.services.embedder.count_tokens(m["content"]) for m in prompt.messages) * PROMPT_TOKEN_MARGIN)
        if estimated + p["max_tokens"] > p["context_window"]:
            raise ValueError(f"The prompt (≈{estimated} tokens) plus Max generated tokens ({p['max_tokens']}) does not fit the "
                             f"context window ({p['context_window']}). Select less evidence or raise the context window.")  # fmt: skip
        options = {"temperature": p["temperature"], "top_p": p["top_p"], "top_k": p["top_k"], "num_ctx": p["context_window"],
                   "num_predict": p["max_tokens"]}  # fmt: skip
        if p["seed"] >= 0:
            options["seed"] = p["seed"]
        start, first_token_ms, parts, usage = time.perf_counter(), None, [], {}
        async for piece in ollama.chat_stream(model, prompt.messages, options, p["thinking"], p["timeout_s"], usage):
            if first_token_ms is None:
                first_token_ms = round((time.perf_counter() - start) * 1000, 1)
            parts.append(piece)
            on_token(piece)
        usage.update(estimated_prompt_tokens=estimated, digest=model.get("digest"), options=options, thinking=p["thinking"])
        return GenerationResult(answer="".join(parts).strip(), model=model["name"], first_token_ms=first_token_ms, usage=usage)
