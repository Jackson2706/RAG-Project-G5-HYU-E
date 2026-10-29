"""PLANNED — ask the LLM to rewrite the question into a clear search query."""

from __future__ import annotations

from app.rag.blocks.query_processing.query_rewriting.base import BaseQueryRewriter
from app.rag.schemas import RewrittenQuery


class LLMQueryRewriter(BaseQueryRewriter):
    async def rewrite(self, question: str) -> RewrittenQuery:
        # TODO:
        # 1. Build a short prompt: "Rewrite this question as a search query: ...".
        # 2. Call the LLM (self.services.ollama.pick_model / chat_stream) with self.params["temperature"].
        # 3. Return RewrittenQuery(query=<rewritten text>); fall back to the question if it is empty.
        raise NotImplementedError("LLM query rewriting is not implemented yet.")
