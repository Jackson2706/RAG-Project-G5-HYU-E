"""Abstract class for Vector Indexing."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock


class BaseVectorIndexer(PipelineBlock):
    """Store the ingested data so it can be searched.

    Input:  document records, chunk records, one vector per chunk, the vector dimension
    Output: None (raise an exception if storing fails)
    """

    @abstractmethod
    def index(self, documents: list[dict], chunks: list[dict], vectors: list[list[float]], dimension: int) -> None: ...
