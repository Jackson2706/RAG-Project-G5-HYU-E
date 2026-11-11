"""IMPLEMENTED — R15 self-query: the LLM reads the question and writes the student's attributes as JSON."""

from __future__ import annotations

import json

from app.rag.aaes import profile_from_llm
from app.rag.applicability import VOCABULARY
from app.rag.blocks.query_processing.query_understanding.base import BaseQueryUnderstanding
from app.rag.schemas import QueryAnalysis

INSTRUCTION = ("Extract the facts the student states about themselves. Reply with one JSON object only, using only these "
               "attributes and values: " + json.dumps({a: list(v) for a, v in VOCABULARY.items()}) +
               ". Leave out every attribute the student does not state. Use \"applicant\" only if they are applying for admission.")  # fmt: skip


class SelfQueryUnderstanding(BaseQueryUnderstanding):
    """Hyperparameters: model, temperature, max_tokens (auxiliary LLM).

    The LLM's values are validated against vocabulary v1; anything else is dropped (listed in the trace).
    With the applicability prefilter this is the self-query retriever: LLM → metadata filter.
    """

    async def analyze(self, question: str, history: list[str] | tuple = ()) -> QueryAnalysis:
        ollama = self.services.ollama
        model = await ollama.pick_model(self.params["model"], self.services.settings.ollama_chat_model)
        said = "\n".join([*(f"Earlier: {t}" for t in history), f"Now: {question}"])
        messages = [{"role": "system", "content": INSTRUCTION}, {"role": "user", "content": said}]
        options = {"temperature": self.params["temperature"], "num_predict": self.params["max_tokens"], "num_ctx": 4096, "seed": 42}
        text, usage = await ollama.complete(model, messages, options)
        profile, dropped = profile_from_llm(text)
        self.trace_details = {"model": model["name"], "raw_output": text[:500], "dropped": dropped,
                              "prompt_tokens": usage.get("prompt_eval_count"), "output_tokens": usage.get("eval_count")}  # fmt: skip
        return QueryAnalysis(profile=profile)
