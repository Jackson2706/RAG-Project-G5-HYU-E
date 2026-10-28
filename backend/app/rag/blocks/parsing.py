"""Block: Parsing — read a file into a title and sections."""

from __future__ import annotations

import re
from abc import abstractmethod
from pathlib import Path

from app.rag.blocks.base import PipelineBlock
from app.rag.blocks.loading import SUPPORTED_TYPES
from app.rag.schemas import ParsedDocument, Section


class BaseDocumentParser(PipelineBlock):
    """Turn one file into readable sections.

    Input:  a file path
    Output: ParsedDocument (title, sections with heading/text/page, declared metadata)
    Raise ValueError if the file has no usable text.
    """

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument: ...

    def source_uri(self, path: Path) -> str:
        """The file's path relative to the data/ folder, e.g. "raw/handbook.pdf"."""
        data_dir = self.services.settings.data_dir.resolve()
        path = path.resolve()
        return path.relative_to(data_dir).as_posix() if path.is_relative_to(data_dir) else path.name


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\t", " ").replace(" ", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class BasicDocumentParser(BaseDocumentParser):
    """IMPLEMENTED — Markdown (split at headings), HTML (h1–h4), TXT (one section), PDF (one section per page)."""

    def parse(self, path: Path) -> ParsedDocument:
        kind = SUPPORTED_TYPES[path.suffix.lower()]
        declared: dict[str, str] = {}
        if kind == "pdf":
            title, sections = self._pdf(path)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            if kind == "md":
                title, sections, declared = self._markdown(text)
            elif kind == "html":
                title, sections, declared = self._html(text)
            else:  # txt: the first line is the title
                title = text.strip().split("\n", 1)[0].strip() or None
                sections = [Section(None, clean(text))]
        sections = [s for s in sections if s.text]
        if not sections:
            raise ValueError("no text could be extracted")
        return ParsedDocument(path=path, source_uri=self.source_uri(path), file_type=kind, title=title or path.stem,
                              sections=sections, declared_metadata=declared)  # fmt: skip

    @staticmethod
    def _markdown(text: str) -> tuple[str | None, list[Section], dict[str, str]]:
        declared: dict[str, str] = {}
        if text.startswith("---\n") and "\n---" in text[4:]:  # front matter: "key: value" lines
            front, text = text[4:].split("\n---", 1)
            for line in front.splitlines():
                key, sep, value = line.partition(":")
                if sep and value.strip():
                    declared[key.strip()] = value.strip().strip("\"'")
        title = declared.pop("title", None)
        sections: list[Section] = []
        heading, lines = None, []
        for line in text.split("\n"):
            match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
            if match:
                if "\n".join(lines).strip():
                    sections.append(Section(heading, clean("\n".join(lines))))
                heading, lines = match.group(1).strip(), []
                title = title or heading
            elif re.match(r"^\s*\|?\s*:?-{3,}", line):
                continue  # table separator row like |---|---|
            elif line.lstrip().startswith("|"):
                lines.append(line.strip().strip("|").strip())  # "| a | b |" -> "a | b"
            else:
                lines.append(line)
        if "\n".join(lines).strip():
            sections.append(Section(heading, clean("\n".join(lines))))
        return title, sections, declared

    @staticmethod
    def _html(html: str) -> tuple[str | None, list[Section], dict[str, str]]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else None
        declared = {m["name"]: m["content"] for m in soup.find_all("meta") if m.get("name") and m.get("content")}
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        sections: list[Section] = []
        heading, parts = None, []
        for el in (soup.body or soup).find_all(["h1", "h2", "h3", "h4", "p", "li", "tr"]):
            if el.name in ("h1", "h2", "h3", "h4"):
                if parts:
                    sections.append(Section(heading, clean("\n".join(parts))))
                heading, parts = el.get_text(" ", strip=True), []
            elif el.name == "tr":
                parts.append(" | ".join(cell.get_text(" ", strip=True) for cell in el.find_all(["th", "td"])))
            else:
                parts.append(("- " if el.name == "li" else "") + el.get_text(" ", strip=True))
        if parts:
            sections.append(Section(heading, clean("\n".join(parts))))
        return title, sections, declared

    @staticmethod
    def _pdf(path: Path) -> tuple[str | None, list[Section]]:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        title = (reader.metadata or {}).get("/Title") or None
        sections = [Section(None, clean(page.extract_text() or ""), page=i) for i, page in enumerate(reader.pages, start=1)]
        return title, [s for s in sections if s.text]


class AdvancedPdfParser(BaseDocumentParser):
    """PLANNED — layout-aware PDF parsing (headings, tables, scanned pages)."""

    def parse(self, path: Path) -> ParsedDocument:
        # TODO:
        # 1. Detect headings by font size, so PDF sections get real headings.
        # 2. Keep tables as tables instead of plain text.
        # 3. Use OCR for scanned pages without text.
        raise NotImplementedError("Advanced PDF parsing is not implemented yet.")
