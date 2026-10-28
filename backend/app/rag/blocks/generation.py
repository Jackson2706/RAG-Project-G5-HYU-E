"""Generation blocks: write the prompt, then let the LLM answer.

    Context Builder   BaseContextBuilder → NumberedContextBuilder (IMPLEMENTED)
    Generation        BaseGenerator      → OllamaGenerator (IMPLEMENTED)
"""

from __future__ import annotations

import time
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import replace

from app.rag.blocks.base import PipelineBlock
from app.rag.schemas import Evidence, GenerationResult, PromptContext

INSUFFICIENT_MARKER = "INSUFFICIENT_CONTEXT"

SYSTEM_PROMPT = f"""You are HYU Compass, a helpful assistant for new students at Hanyang University.
Answer ONLY with information from the evidence blocks provided with the question.
Rules:
- After every fact, cite the evidence it comes from, like [E1] or [E1][E3].
- Use only evidence labels that appear below. Never invent sources, dates or numbers.
- If the evidence does not answer the question, reply with {INSUFFICIENT_MARKER} on the first line, then one sentence explaining what is missing.
- Write clear, short English in Markdown."""


class BaseContextBuilder(PipelineBlock):
    """Write the prompt.  Input: question + selected Evidence.  Output: PromptContext (messages, labelled evidence)."""

    @abstractmethod
    async def build(self, question: str, evidence: list[Evidence]) -> PromptContext: ...


class NumberedContextBuilder(BaseContextBuilder):
    """IMPLEMENTED — evidence as blocks "[E1] title — section — page" + text, plus the grounding rules."""

    async def build(self, question: str, evidence: list[Evidence]) -> PromptContext:
        labelled = [replace(e, label=f"E{i}") for i, e in enumerate(evidence, start=1)]
        blocks = []
        for e in labelled:
            where = " — ".join(p for p in [e.title, e.section, f"page {e.page_number}" if e.page_number else None] if p)
            blocks.append(f"[{e.label}] {where}\n{e.text}")
        context = "\n\n".join(blocks)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Evidence:\n{context}\n\nQuestion: {question}"},
        ]
        tokens = self.services.embedder.count_tokens(context)  # measured with the embedding tokenizer
        return PromptContext(messages=messages, context_text=context, evidence=labelled, token_count=tokens)


class BaseGenerator(PipelineBlock):
    """Write the answer.

    Input:  PromptContext, and `on_token`: call it with every new piece of text (for live streaming)
    Output: GenerationResult (full answer, model name)
    """

    @abstractmethod
    async def generate(self, prompt: PromptContext, on_token: Callable[[str], None]) -> GenerationResult: ...


class OllamaGenerator(BaseGenerator):
    """IMPLEMENTED — a local Ollama chat model, streamed. Hyperparameters: model, temperature, max_tokens."""

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
