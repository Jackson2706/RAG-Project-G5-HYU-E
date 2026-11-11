"""IMPLEMENTED — G0 closed-book bracket: the question alone, no evidence."""

from __future__ import annotations

from app.rag.blocks.grounded_generation.context_construction.standard_context import StandardContextBuilder
from app.rag.schemas import Evidence, PromptContext

CLOSED_BOOK_PROMPT = ("You are HYU Compass, a helpful assistant for new students at Hanyang University. Answer from your own "
                      "knowledge; no documents are provided. If you do not know, say so. Write clear, short English in Markdown.")  # fmt: skip


class ClosedBookBuilder(StandardContextBuilder):
    """G0 bracket: the question alone, no evidence in the prompt, so nothing can be cited.
    shortcut: retrieval still runs before this step (wasted work, results unused); skip it if G0 latency matters."""

    async def build(self, question: str, evidence: list[Evidence]) -> PromptContext:
        messages = [{"role": "system", "content": CLOSED_BOOK_PROMPT}, {"role": "user", "content": question}]
        return PromptContext(messages=messages, context_text="", evidence=[], token_count=0)
