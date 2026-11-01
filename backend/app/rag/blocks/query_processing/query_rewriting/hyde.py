"""IMPLEMENTED — HyDE: embed a hypothetical answer passage instead of the question (Gao et al., 2023)."""

from __future__ import annotations

from app.rag.blocks.query_processing.query_rewriting.base import BaseQueryRewriter
from app.rag.schemas import RewrittenQuery

INSTRUCTION = ("Write a short passage (about 80 words) in the style of a reference document that would answer the "
               "user's question. Write only the passage.")  # fmt: skip


class HyDERewriter(BaseQueryRewriter):
    """Hyperparameters: model, temperature, max_tokens.

    The LLM invents a document-like passage; dense retrieval embeds THAT passage (as a document) and
    finds real chunks near it. The passage may contain wrong facts — it is only a search vector:
    it is never evidence, never shown as a source and never cited. Lexical retrieval and the answer
    keep using the original question.
    """

    async def rewrite(self, question: str) -> RewrittenQuery:
        ollama = self.services.ollama
        model = await ollama.pick_model(self.params["model"], self.services.settings.ollama_chat_model)
        messages = [{"role": "system", "content": INSTRUCTION}, {"role": "user", "content": question}]
        options = {"temperature": self.params["temperature"], "num_predict": self.params["max_tokens"], "num_ctx": 4096, "seed": 42}
        text, usage = await ollama.complete(model, messages, options)
        self.trace_details = {"model": model["name"], "prompt_tokens": usage.get("prompt_eval_count"), "output_tokens": usage.get("eval_count")}
        if not text.strip():
            return RewrittenQuery(query=question, validation={"passed": False, "reason": "empty passage; using the question"})
        return RewrittenQuery(query=question, embedding_text=text.strip(),
                              validation={"passed": True, "reason": "hypothetical passage used for dense retrieval only"})
