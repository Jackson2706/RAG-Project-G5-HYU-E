"""IMPLEMENTED — HyDE: embed a hypothetical answer passage instead of the question (Gao et al., 2023)."""

from __future__ import annotations

import json
import re

from app.rag.blocks.query_processing.query_rewriting.base import BaseQueryRewriter, required_terms
from app.rag.schemas import RewrittenQuery

INSTRUCTION = (
    "Write a concise, hypothetical reference-style passage for dense retrieval based on the user's question. "
    "Use only the entities and topic stated in the question. Do not invent a university, location, deadline, "
    "eligibility rule, application step, or other specific fact. Do not answer with advice or explain your reasoning. "
    "Write 1-3 short sentences, no more than 60 words. Return only a JSON object with one string field named 'passage'."
)
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"passage": {"type": "string"}},
    "required": ["passage"],
    "additionalProperties": False,
}
REASONING_MARKERS = (
    "the user is asking",
    "we are given",
    "i need to",
    "i should",
    "i remember",
    "let me",
    "first,",
    "steps:",
    "word count",
    "i will",
)


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
        text, usage = await ollama.complete(model, messages, options, format=OUTPUT_SCHEMA)
        try:
            response = json.loads(text)
            raw_passage = response.get("passage") if isinstance(response, dict) else None
        except json.JSONDecodeError:
            raw_passage = None

        passage = raw_passage.strip() if isinstance(raw_passage, str) else ""
        words = re.findall(r"\b[\w'-]+\b", passage)
        lowered = passage.lower()
        missing_terms = [term for term in required_terms(question) if term.lower() not in lowered]
        reason = None
        if not passage:
            reason = "invalid JSON or empty passage"
        elif len(words) > 60:
            reason = "passage exceeded 60 words"
        elif len(words) < 5:
            reason = "passage was too short"
        elif any(marker in lowered for marker in REASONING_MARKERS):
            reason = "reasoning text was returned instead of a passage"
        elif missing_terms:
            reason = f"passage omitted required question terms: {', '.join(missing_terms)}"

        self.trace_details = {
            "model": model["name"],
            "prompt_tokens": usage.get("prompt_eval_count"),
            "output_tokens": usage.get("eval_count"),
        }
        if reason:
            self.trace_details["fallback_reason"] = reason
            return RewrittenQuery(query=question, validation={"passed": False, "reason": f"{reason}; using the question"})
        return RewrittenQuery(
            query=question,
            embedding_text=passage,
            validation={"passed": True, "reason": "hypothetical passage used for dense retrieval only"},
        )
