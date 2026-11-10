"""Abstract class for Parsing."""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import ParsedDocument


class BaseDocumentParser(PipelineBlock):
    """Turn one file into readable sections.

    Input:  a file path
    Output: ParsedDocument (title, sections with heading/text/page, declared metadata)
    Raise ValueError if the file has no usable text.
    """

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument: ...

    def source_uri(self, path: Path) -> str:
        """The file's path relative to DATA_DIR, e.g. "HYU/raw/handbook.pdf" (sample documents: "sample_data/<file>")."""
        from app.config import SAMPLE_DATA_DIR, SAMPLE_FOLDER

        data_dir = self.services.settings.data_dir.resolve()
        path = path.resolve()
        if path.is_relative_to(data_dir):
            return path.relative_to(data_dir).as_posix()
        if path.is_relative_to(SAMPLE_DATA_DIR.resolve()):
            return f"{SAMPLE_FOLDER}/{path.relative_to(SAMPLE_DATA_DIR.resolve()).as_posix()}"
        return path.name
