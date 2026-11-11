"""IMPLEMENTED — R16 prompted-conditional: the standard evidence blocks plus an 'answer per case or ask' rule."""

from __future__ import annotations

from app.rag.blocks.grounded_generation.context_construction.standard_context import SYSTEM_PROMPT, StandardContextBuilder
from app.rag.schemas import Evidence, PromptContext

CONDITIONAL_RULE = ("\n- Some rules apply only to some students (campus, degree level, year, student type, visa, TOPIK level, "
                    "English track, academic status). If the answer depends on facts the student has not given, state the answer "
                    "for each case (\"If you are …\") or ask ONE short clarifying question. If no evidence applies to the student, "
                    "say so and refer them to the OIA office of their campus.")  # fmt: skip


class ConditionalPromptBuilder(StandardContextBuilder):
    """R16: the standard evidence blocks, plus one instruction to answer per case or ask (no AAES machinery)."""

    async def build(self, question: str, evidence: list[Evidence]) -> PromptContext:
        prompt = await super().build(question, evidence)
        prompt.messages[0] = {"role": "system", "content": SYSTEM_PROMPT + CONDITIONAL_RULE}
        return prompt
