"""Parsers for Markdown, plain text, HTML and PDF.

Every parser emits ordered blocks (heading / paragraph / list / table) with a
section path and page number. `_assemble` normalizes each block and joins them
with blank lines into ``content``; block spans are offsets into that string.

Provenance limitation (recorded, not hidden): spans refer to the *normalized*
text stored in MongoDB, not to raw file bytes. For Markdown/TXT the difference
is only line endings, Unicode NFC, trailing whitespace and markup characters
(e.g. '#', '|'). For HTML/PDF the raw bytes have no meaningful text offsets.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.models.documents import BlockKind, ParsedBlock, ParsedDocument, SourceSpan

PARSER_REVISION = "v1"
HEADING_MD = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
LIST_MD = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


@dataclass
class _Block:
    kind: BlockKind
    text: str
    section_path: list[str] = field(default_factory=list)
    page_number: int | None = None


def parser_id(file_type: str, method: str) -> str:
    return f"{file_type}-{method}-{PARSER_REVISION}"


def normalize_text(text: str, nfc: bool = True) -> str:
    if nfc:
        text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ").replace(" ", " ")
    lines = [re.sub(r" {2,}", " ", line).rstrip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _assemble(blocks: list[_Block], nfc: bool) -> tuple[str, list[ParsedBlock]]:
    parts: list[str] = []
    parsed: list[ParsedBlock] = []
    cursor = 0
    for b in blocks:
        text = normalize_text(b.text, nfc)
        if not text:
            continue
        if parts:
            cursor += 2  # "\n\n" separator
        parsed.append(ParsedBlock(kind=b.kind, text=text, section_path=b.section_path, page_number=b.page_number,
                                  span=SourceSpan(start=cursor, end=cursor + len(text))))  # fmt: skip
        parts.append(text)
        cursor += len(text)
    return "\n\n".join(parts), parsed


class _SectionStack:
    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def push(self, level: int, title: str) -> list[str]:
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        self._stack.append((level, title))
        return self.path

    @property
    def path(self) -> list[str]:
        return [t for _, t in self._stack]


# ---------------------------------------------------------------- Markdown / text


def _split_front_matter(text: str) -> tuple[dict[str, Any], str, list[str]]:
    if not text.startswith("---\n"):
        return {}, text, []
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text, ["front matter start '---' has no closing '---'; treated as text"]
    try:
        data = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError as exc:
        return {}, text[end + 4 :], [f"front matter is not valid YAML: {exc}"]
    if not isinstance(data, dict):
        return {}, text[end + 4 :], ["front matter is not a key/value mapping; ignored"]
    return data, text[end + 4 :].lstrip("\n"), []


def _markdown_blocks(text: str, structured: bool, preserve_tables: bool) -> list[_Block]:
    blocks: list[_Block] = []
    sections = _SectionStack()
    buf: list[str] = []
    buf_kind: BlockKind = "paragraph"
    in_fence = False

    def flush() -> None:
        nonlocal buf
        if buf:
            lines = [ln for ln in buf if not (buf_kind == "table" and TABLE_SEPARATOR.match(ln))]
            if buf_kind == "table":
                lines = [" | ".join(c.strip() for c in ln.strip().strip("|").split("|")) for ln in lines]
            blocks.append(_Block(buf_kind, "\n".join(lines), sections.path if structured else []))
        buf = []

    for line in text.split("\n"):
        if line.strip().startswith("```"):
            if not in_fence:
                flush()
                buf_kind = "paragraph"
            in_fence = not in_fence
            continue
        if in_fence:
            buf.append(line)
            continue
        if not line.strip():
            flush()
            continue
        heading = HEADING_MD.match(line)
        if heading:
            flush()
            title = heading.group(2).strip()
            if structured:
                path = sections.push(len(heading.group(1)), title)
                blocks.append(_Block("heading", title, path))
            else:
                blocks.append(_Block("paragraph", title))
            continue
        kind: BlockKind = "paragraph"
        if line.lstrip().startswith("|"):
            kind = "table" if preserve_tables and structured else "paragraph"
        elif LIST_MD.match(line):
            kind = "list" if structured else "paragraph"
        elif buf and buf_kind == "list" and line.startswith((" ", "\t")):
            kind = "list"  # list item continuation
        if buf and kind != buf_kind:
            flush()
        buf_kind = kind
        buf.append(line)
    flush()
    return blocks


def _text_blocks(text: str) -> list[_Block]:
    return [_Block("paragraph", p) for p in re.split(r"\n\s*\n", text) if p.strip()]


# ---------------------------------------------------------------- HTML

HTML_BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "pre", "blockquote", "dl"}
HTML_META_KEYS = {"description", "keywords", "campus", "audience", "document_type", "academic_year", "issuer",
                  "publication_date", "effective_from", "effective_until", "topics", "dc.date", "dc.title"}  # fmt: skip


def _parse_html(raw: str, structured: bool, preserve_tables: bool) -> tuple[str | None, dict[str, Any], list[_Block], list[str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    declared: dict[str, Any] = {}
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").strip().lower()
        if name in HTML_META_KEYS and meta.get("content"):
            declared[{"dc.date": "publication_date", "dc.title": "title"}.get(name, name)] = meta["content"]
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        declared.setdefault("language", html_tag["lang"].split("-")[0].lower())
    title = soup.title.get_text(strip=True) if soup.title else None
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    body = soup.body or soup
    blocks: list[_Block] = []
    sections = _SectionStack()
    for el in body.find_all(HTML_BLOCK_TAGS):
        if any(parent.name in HTML_BLOCK_TAGS for parent in el.parents):
            continue  # nested inside a block already emitted
        name = el.name
        if name[0] == "h" and name[1:].isdigit():
            text = el.get_text(" ", strip=True)
            if structured:
                blocks.append(_Block("heading", text, sections.push(int(name[1]), text)))
            else:
                blocks.append(_Block("paragraph", text))
        elif name in ("ul", "ol"):
            items = [li.get_text(" ", strip=True) for li in el.find_all("li")]
            blocks.append(_Block("list" if structured else "paragraph", "\n".join(f"- {i}" for i in items if i), sections.path if structured else []))
        elif name == "table":
            rows = [" | ".join(c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])) for tr in el.find_all("tr")]
            kind: BlockKind = "table" if structured and preserve_tables else "paragraph"
            blocks.append(_Block(kind, "\n".join(r for r in rows if r.strip()), sections.path if structured else []))
        else:
            blocks.append(_Block("paragraph", el.get_text(" ", strip=True), sections.path if structured else []))
    warnings: list[str] = []
    body_len = len(body.get_text(" ", strip=True))
    block_len = sum(len(b.text) for b in blocks)
    if not blocks and body_len:
        blocks = [_Block("paragraph", body.get_text("\n", strip=True))]
        warnings.append("no block-level elements found; used the full body text without structure")
    elif body_len and block_len < 0.6 * body_len:
        warnings.append(f"block elements cover only {block_len / body_len:.0%} of body text; text outside p/li/table/h* was not captured")
    if not title:
        title = next((b.text for b in blocks if b.kind == "heading"), None)
    return title, declared, blocks, warnings


# ---------------------------------------------------------------- PDF


def _parse_pdf(path: Path) -> tuple[str | None, dict[str, Any], list[_Block], int, list[str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ValueError("PDF is encrypted; decryption is not attempted")
    info = reader.metadata or {}
    title = (info.get("/Title") or "").strip() or None
    declared: dict[str, Any] = {}
    if info.get("/Subject"):
        declared["description"] = str(info["/Subject"])
    blocks: list[_Block] = []
    warnings = ["PDF parsing extracts text per page; headings and table structure are not detected"]
    for number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            warnings.append(f"page {number} has no extractable text (scanned image?)")
            continue
        paragraphs = [p for p in re.split(r"\n\s*\n", page_text) if p.strip()] or [page_text]
        blocks.extend(_Block("paragraph", p, page_number=number) for p in paragraphs)
    return title, declared, blocks, len(reader.pages), warnings


# ---------------------------------------------------------------- entry point


def parse_file(path: Path, file_type: str, method: str, params: dict[str, Any]) -> ParsedDocument:
    if method not in ("structure_aware", "basic"):
        raise ValueError(f"parsing method '{method}' is not implemented")
    structured = method == "structure_aware"
    preserve_tables = params.get("preserve_tables", True)
    nfc = params.get("normalize_unicode", True)
    declared: dict[str, Any] = {}
    warnings: list[str] = []
    page_count = None
    if file_type == "pdf":
        title, declared, blocks, page_count, warnings = _parse_pdf(path)
    else:
        raw = path.read_bytes().decode("utf-8-sig", errors="replace")
        if "�" in raw:
            warnings.append("file is not valid UTF-8; undecodable bytes were replaced")
        if file_type == "html":
            title, declared, blocks, warnings2 = _parse_html(raw, structured, preserve_tables)
            warnings += warnings2
        else:
            raw = raw.replace("\r\n", "\n")
            if file_type == "md":
                declared, body, warnings = _split_front_matter(raw)
                blocks = _markdown_blocks(body, structured, preserve_tables)
                title = declared.get("title") or next((b.text for b in blocks if b.kind == "heading"), None)
            else:
                blocks = _text_blocks(raw)
                first = blocks[0].text.strip().split("\n")[0] if blocks else ""
                title = first if 0 < len(first) <= 120 else None
    content, parsed = _assemble(blocks, nfc)
    if not content:
        raise ValueError("no extractable text")
    return ParsedDocument(title=str(title).strip() if title else None, content=content, blocks=parsed,
                          page_count=page_count, declared_metadata=declared,
                          parser_id=parser_id(file_type, method), warnings=warnings)  # fmt: skip
