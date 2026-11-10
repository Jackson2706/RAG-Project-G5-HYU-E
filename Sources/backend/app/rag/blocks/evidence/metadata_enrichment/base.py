"""Abstract class for Metadata Enrichment (chunk lookup)."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import Candidate, Evidence


class BaseMetadataEnricher(PipelineBlock):
    """Input: Candidates (IDs + scores). Output: Evidence (with text, title, section, page)."""

    @abstractmethod
    async def enrich(self, candidates: list[Candidate]) -> list[Evidence]: ...
