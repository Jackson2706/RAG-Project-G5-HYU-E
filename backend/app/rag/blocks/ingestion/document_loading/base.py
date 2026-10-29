"""Abstract class for Document Loading."""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path

from app.rag.blocks.pipeline_block import PipelineBlock

SUPPORTED_TYPES = {".pdf": "pdf", ".txt": "txt", ".md": "md", ".markdown": "md", ".html": "html", ".htm": "html"}


class BaseDocumentLoader(PipelineBlock):
    """Find the documents to ingest.

    Input:  a folder path
    Output: (files to ingest, messages about skipped files)
    """

    @abstractmethod
    def load(self, folder: Path) -> tuple[list[Path], list[str]]: ...
