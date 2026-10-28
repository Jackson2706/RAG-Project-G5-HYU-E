"""Block: Document Loading — which files should be ingested?"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path

from app.rag.blocks.base import PipelineBlock

SUPPORTED_TYPES = {".pdf": "pdf", ".txt": "txt", ".md": "md", ".markdown": "md", ".html": "html", ".htm": "html"}
SKIPPED_NAMES = {"README.md", ".DS_Store", ".gitkeep"}


class BaseDocumentLoader(PipelineBlock):
    """Find the documents to ingest.

    Input:  a folder path
    Output: (files to ingest, messages about skipped files)
    """

    @abstractmethod
    def load(self, folder: Path) -> tuple[list[Path], list[str]]: ...


class LocalFolderLoader(BaseDocumentLoader):
    """IMPLEMENTED — every supported file in the folder and its sub-folders, sorted by path."""

    def load(self, folder: Path) -> tuple[list[Path], list[str]]:
        if not folder.exists():
            raise FileNotFoundError(f"Folder not found: {folder}")
        files, skipped = [], []
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.name in SKIPPED_NAMES or path.name.startswith("."):
                continue
            if path.suffix.lower() in SUPPORTED_TYPES:
                files.append(path)
            else:
                skipped.append(f"{path.name}: unsupported file type")
        return files, skipped


class WebsiteLoader(BaseDocumentLoader):
    """PLANNED — download approved pages from the HYU website."""

    def load(self, folder: Path) -> tuple[list[Path], list[str]]:
        # TODO:
        # 1. Read a list of approved page URLs (never bypass logins or download limits).
        # 2. Download each page into `folder` as an .html file.
        # 3. Return the saved paths, like LocalFolderLoader does.
        raise NotImplementedError("Website loading is not implemented yet.")
