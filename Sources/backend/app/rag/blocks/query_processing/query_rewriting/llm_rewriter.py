"""IMPLEMENTED — the LLM rewrites the question into one search query, which is then checked."""

from __future__ import annotations

from app.rag.blocks.query_processing.query_rewriting.base import BaseQueryRewriter, clean_query, validate_rewrite
from app.rag.schemas import RewrittenQuery

INSTRUCTION = ("Rewrite the user's question as one concise search query for a document search engine. "
               "Keep every name, number, date, quoted phrase and negation exactly. Do not add facts or answer the question. "
               "Reply with the search query only.")  # fmt: skip


class LLMQueryRewriter(BaseQueryRewriter):
    """Hyperparameters: model (auxiliary Ollama model), temperature, max_tokens.

    The rewrite must pass validate_rewrite() (required terms kept, no lost negation, sensible length);
    otherwise retrieval uses the original question. The original question is always kept for the answer.
    """

    async def rewrite(self, question: str) -> RewrittenQuery:
        ollama = self.services.ollama
        model = await ollama.pick_model(self.params["model"], self.services.settings.ollama_chat_model)
        messages = [{"role": "system", "content": INSTRUCTION}, {"role": "user", "content": question}]
        options = {"temperature": self.params["temperature"], "num_predict": self.params["max_tokens"], "num_ctx": 4096, "seed": 42}
        text, usage = await ollama.complete(model, messages, options)
        candidate = clean_query(text.splitlines()[0] if text.strip() else "")
        check = validate_rewrite(question, candidate)
        self.trace_details = {"model": model["name"], "raw_output": text[:500], "prompt_tokens": usage.get("prompt_eval_count"),
                              "output_tokens": usage.get("eval_count")}  # fmt: skip
        if not check["passed"]:
            return RewrittenQuery(query=question, validation={**check, "rejected_rewrite": candidate, "used": "original question"})
        return RewrittenQuery(query=candidate, validation={**check, "used": "rewrite"})
