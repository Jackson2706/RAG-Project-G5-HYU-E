"""PLANNED — generate several paraphrases of the question."""

from __future__ import annotations

from app.rag.blocks.query_processing.query_rewriting.base import BaseQueryRewriter
from app.rag.schemas import RewrittenQuery


class MultiQueryRewriter(BaseQueryRewriter):
    async def rewrite(self, question: str) -> RewrittenQuery:
        # TODO:
        # 1. Ask the LLM for self.params["num_queries"] different phrasings of the question.
        # 2. Return RewrittenQuery(query=question, alternatives=[...]).
        # 3. Retrieval for the alternatives (and merging the results) must then be added to the runner.
        raise NotImplementedError("Multi-query rewriting is not implemented yet.")
