"""IMPLEMENTED — title, language and the fields a file declares itself."""

from __future__ import annotations

from app.rag.blocks.ingestion.metadata_extraction.base import BaseMetadataExtractor
from app.rag.schemas import DocumentMetadata, ParsedDocument


class BasicMetadataExtractor(BaseMetadataExtractor):
    """Title from parsing, language "en", plus declared fields (Markdown front matter such as
    `campus: ERICA`, or HTML <meta name=… content=…> tags)."""

    def extract(self, document: ParsedDocument) -> DocumentMetadata:
        return DocumentMetadata(title=document.title, language="en", extra=dict(document.declared_metadata))
