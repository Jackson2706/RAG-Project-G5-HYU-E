"""IMPLEMENTED — multi-query expansion: several complementary search queries, each searched separately."""

from __future__ import annotations

import json

from app.rag.blocks.query_processing.query_rewriting.base import BaseQueryRewriter, clean_query, validate_rewrite
from app.rag.schemas import RewrittenQuery

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
    "additionalProperties": False,
}


class MultiQueryRewriter(BaseQueryRewriter):
    """Hyperparameters: model, num_queries, include_original, rrf_k, temperature, max_tokens.

    The LLM writes `num_queries` different search queries for the same question. Each is checked with
    validate_rewrite(); invalid ones are dropped. The pipeline then runs every retriever once PER
    QUERY and merges the rankings with Reciprocal Rank Fusion (rrf_k) — so this costs one LLM call
    plus (number of queries) searches, not one search.
    """

    async def rewrite(self, question: str) -> RewrittenQuery:
        ollama, n = self.services.ollama, self.params["num_queries"]
        model = await ollama.pick_model(self.params["model"], self.services.settings.ollama_chat_model)
        instruction = (
            f"Generate {n} concise, distinct, keyword-based search queries for the user's question. "
            "Remove conversational wording. Preserve every proper name, number, date, quoted phrase, and negation. "
            "Do not answer the question. Each query must be a search phrase, not an explanation or a sentence about the task. "
            "Return only a JSON object with a 'queries' array of strings. Do not include reasoning or other text."
        )  # fmt: skip
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": question}
        ]
        options = {"temperature": self.params["temperature"], "num_predict": self.params["max_tokens"], "num_ctx": 4096, "seed": 42}
        text, usage = await ollama.complete(model, messages, options, format=OUTPUT_SCHEMA)
        kept, rejected = [], []
        try:
            response = json.loads(text)
            raw_queries = response.get("queries") if isinstance(response, dict) else None
        except json.JSONDecodeError:
            raw_queries = None
        if not isinstance(raw_queries, list):
            raw_queries = None

        if isinstance(raw_queries, list):
            for raw_query in raw_queries:
                if not isinstance(raw_query, str):
                    continue
                query = clean_query(raw_query)
                if not query or query.lower() in (q.lower() for q in kept) or query.lower() == question.lower():
                    continue
                check = validate_rewrite(question, query)
                (kept if check["passed"] else rejected).append(query if check["passed"] else {"query": query, "reason": check["reason"]})
        kept = kept[:n]
        self.trace_details = {"model": model["name"], "prompt_tokens": usage.get("prompt_eval_count"),
                              "output_tokens": usage.get("eval_count"), "rejected": rejected}  # fmt: skip
        validation = {"passed": bool(kept), "generated": len(kept) + len(rejected), "kept": len(kept), "rejected": len(rejected),
                      "reason": f"{len(kept)} of {len(kept) + len(rejected)} generated queries kept"}  # fmt: skip
        if raw_queries is None:
            validation["reason"] = "invalid JSON response; no alternative queries accepted"
        if self.params["include_original"] or not kept:
            return RewrittenQuery(query=question, alternatives=kept, validation=validation)
        return RewrittenQuery(query=kept[0], alternatives=kept[1:], validation=validation)
