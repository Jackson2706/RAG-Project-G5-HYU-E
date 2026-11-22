"""PLANNED — ask the LLM for campus, audience, deadlines, …"""

from __future__ import annotations

from app.rag.blocks.ingestion.metadata_extraction.base import BaseMetadataExtractor
from app.rag.schemas import DocumentMetadata, ParsedDocument


class LLMMetadataExtractor(BaseMetadataExtractor):
    def extract(self, document: ParsedDocument) -> DocumentMetadata:
        # TODO:
        # 1. Send the first sections to the LLM (self.services.ollama) with a JSON-only prompt.
        # 2. Keep only fields with allowed values (e.g. campus in {"SEOUL", "ERICA", "ALL"}).
        # 3. Record which values came from the LLM, so they can be checked.
        raise NotImplementedError("LLM metadata extraction is not implemented yet.")
