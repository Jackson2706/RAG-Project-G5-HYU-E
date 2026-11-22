"""IMPLEMENTED — load files from a local folder."""

from __future__ import annotations

from pathlib import Path

from app.rag.blocks.ingestion.document_loading.base import SUPPORTED_TYPES, BaseDocumentLoader

SKIPPED_NAMES = {"README.md", ".DS_Store", ".gitkeep"}


class LocalFolderLoader(BaseDocumentLoader):
    """Every supported file (PDF, TXT, Markdown, HTML) in the folder and its sub-folders, sorted by path."""

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
