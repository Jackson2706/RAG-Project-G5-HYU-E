"""Abstract class for Metadata Extraction."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import DocumentMetadata, ParsedDocument


class BaseMetadataExtractor(PipelineBlock):
    """Describe a document.

    Input:  ParsedDocument
    Output: DocumentMetadata (title, language, extra fields). Never guess unknown values.
    """

    @abstractmethod
    def extract(self, document: ParsedDocument) -> DocumentMetadata: ...
