"""IMPLEMENTED — numbered evidence blocks plus the grounding rules."""

from __future__ import annotations

from app.rag.blocks.grounded_generation.context_construction.base import BaseContextBuilder
from app.rag.schemas import INSUFFICIENT_MARKER, Evidence, PromptContext

SYSTEM_PROMPT = f"""You are HYU Compass, a helpful assistant for new students at Hanyang University.
Answer ONLY with information from the evidence blocks provided with the question.
Rules:
- After every fact, write the label of the evidence it comes from, like [E1] or [E1][E3].
- Use only evidence labels that appear below. Never invent sources, dates or numbers.
- If the evidence does not answer the question, reply with {INSUFFICIENT_MARKER} on the first line, then one sentence explaining what is missing.
- Write clear, short English in Markdown."""


class StandardContextBuilder(BaseContextBuilder):
    """Blocks like "[E1] title — section — page" followed by the chunk text."""

    async def build(self, question: str, evidence: list[Evidence]) -> PromptContext:
        labelled = [e.model_copy(update={"label": f"E{i}"}) for i, e in enumerate(evidence, start=1)]
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
