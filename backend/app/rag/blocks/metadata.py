"""Block: Metadata Extraction — facts about a document (title, language, campus, …)."""

from __future__ import annotations

from abc import abstractmethod

from app.rag.blocks.base import PipelineBlock
from app.rag.schemas import DocumentMetadata, ParsedDocument


class BaseMetadataExtractor(PipelineBlock):
    """Describe a document.

    Input:  ParsedDocument
    Output: DocumentMetadata (title, language, extra fields). Never guess unknown values.
    """

    @abstractmethod
    def extract(self, document: ParsedDocument) -> DocumentMetadata: ...


class BasicMetadataExtractor(BaseMetadataExtractor):
    """IMPLEMENTED — the title from the parser, language "en", plus fields the file declares itself
    (Markdown front matter such as `campus: ERICA`, or HTML <meta name=… content=…> tags)."""

    def extract(self, document: ParsedDocument) -> DocumentMetadata:
        return DocumentMetadata(title=document.title, language="en", extra=dict(document.declared_metadata))


class LLMMetadataExtractor(BaseMetadataExtractor):
    """PLANNED — ask the LLM for campus, audience, deadlines, …"""

    def extract(self, document: ParsedDocument) -> DocumentMetadata:
        # TODO:
        # 1. Send the first sections to the LLM (self.services.ollama) with a JSON-only prompt.
        # 2. Keep only fields with allowed values (e.g. campus in {"SEOUL", "ERICA"}).
        # 3. Store where each value came from, so it can be checked.
        raise NotImplementedError("LLM metadata extraction is not implemented yet.")
