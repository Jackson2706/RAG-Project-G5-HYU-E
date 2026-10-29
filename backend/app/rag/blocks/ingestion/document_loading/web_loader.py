"""PLANNED — download approved pages from the HYU website."""

from __future__ import annotations

from pathlib import Path

from app.rag.blocks.ingestion.document_loading.base import BaseDocumentLoader


class WebsiteLoader(BaseDocumentLoader):
    def load(self, folder: Path) -> tuple[list[Path], list[str]]:
        # TODO:
        # 1. Read a list of approved page URLs (never bypass logins or download limits).
        # 2. Download each page into `folder` as an .html file.
        # 3. Return the saved paths, like LocalFolderLoader does.
        raise NotImplementedError("Website loading is not implemented yet.")
