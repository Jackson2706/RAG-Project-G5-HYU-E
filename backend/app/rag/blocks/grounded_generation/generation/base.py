"""Abstract class for Generation."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import GenerationResult, PromptContext


class BaseGenerator(PipelineBlock):
    """Write the answer.

    Input:  PromptContext, and `on_token`: call it with every new piece of text (for live streaming)
    Output: GenerationResult (full answer, model name)
    """

    @abstractmethod
    async def generate(self, prompt: PromptContext, on_token: Callable[[str], None]) -> GenerationResult: ...
