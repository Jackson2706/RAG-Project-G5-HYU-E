"""Abstract class for Embedding.

The same embedder must be used for documents (ingestion) and questions (retrieval):
vectors from different models cannot be compared.
"""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock


class BaseEmbedder(PipelineBlock):
    """Input: texts. Output: one vector (list[float]) per text, all of length `dimension()`."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, question: str) -> list[float]: ...

    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        """Character (start, end) of every token — used to measure chunks in real tokens."""

    def count_tokens(self, text: str) -> int:
        return len(self.token_offsets(text))
