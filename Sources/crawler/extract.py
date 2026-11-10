"""Pure extraction helpers for HTML pages and supported attachments."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import unicodedata
import uuid
import zipfile
from xml.etree import ElementTree as ET
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, NavigableString, Tag
from pypdf import PdfReader

from .sites import ERICA_BOARD_NAMES, SITES, SiteConfig, get_site


EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
DATE_RE = re.compile(r"(?<!\d)(20\d{2})[./-](\d{1,2})[./-](\d{1,2})(?!\d)")
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt"}
# A page that keeps only its title (e.g. "VISA") is not a useful English document.
MIN_ENGLISH_LETTERS = 30


@dataclass(frozen=True)
class TextBlock:
    text: str
    kind: str


@dataclass(frozen=True)
class AttachmentInput:
    data: bytes
    filename: str
    content_type: str = ""
    canonical_uri: str = ""
    sha256: str = ""


def canonical_uri(url: str) -> str:
    """Return the stable crawler identity for a page or attachment URL."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    query = parse_qs(parsed.query, keep_blank_values=True)

    if host == "oia.hanyang.ac.kr":
        file_srl = query.get("file_srl", [None])[0]
        is_download = query.get("act", [""])[0] == "procFileDownload"
        is_output = path.rstrip("/").endswith("/file/procFileOutput")
        if file_srl and (is_download or is_output):
            return urlunsplit(
                ("https", host, "/", urlencode((
                    ("module", "file"),
                    ("act", "procFileDownload"),
                    ("file_srl", file_srl),
                )), "")
            )
        for key in ("page", "sort_index", "order_type", "mid"):
            query.pop(key, None)
        flat_query = [(key, value) for key in sorted(query) for value in query[key]]
        return urlunsplit(("https", host, path, urlencode(flat_query), ""))

    if host == "global.hanyang.ac.kr":
        if path == "/bbs/board.php":
            kept = []
            for key in ("bo_table", "wr_id"):
                if key in query:
                    kept.append((key, query[key][0]))
            return urlunsplit(("https", host, path, urlencode(kept), ""))
        if path == "/bbs/download.php":
            kept = []
            for key in ("bo_table", "wr_id", "no"):
                if key in query:
                    kept.append((key, query[key][0]))
            return urlunsplit(("https", host, path, urlencode(kept), ""))
        return urlunsplit(("https", host, path, "", ""))

    return urlunsplit(("https", host, path, parsed.query, ""))


def doc_id_for_url(url: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_uri(url)))


def is_hangul_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x1100 <= code <= 0x11FF
        or 0x3130 <= code <= 0x318F
        or 0xAC00 <= code <= 0xD7AF
        or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0x3040 <= code <= 0x30FF
        or 0x31F0 <= code <= 0x31FF
    )


def is_latin(char: str) -> bool:
    if not char.isalpha():
        return False
    try:
        return "LATIN" in unicodedata.name(char)
    except ValueError:
        return False


def language_counts(texts: list[str]) -> dict[str, int | float]:
    text = "\n".join(texts)
    total = sum(char.isalpha() for char in text)
    english = sum(is_latin(char) for char in text)
    return {
        "en_letters": english,
        "total_letters": total,
        "ratio": english / total if total else 0.0,
    }


def filter_english_blocks(blocks: list[TextBlock]) -> tuple[list[TextBlock], list[str]]:
    kept: list[TextBlock] = []
    previous_non_neutral_kept = False
    borderline = 0
    for block in blocks:
        letters = sum(char.isalpha() for char in block.text)
        non_latin = sum(is_hangul_cjk(char) for char in block.text)
        latin = sum(is_latin(char) for char in block.text)
        neutral = non_latin == 0 and letters < 3
        if neutral:
            if previous_non_neutral_kept:
                kept.append(block)
            continue
        keep = bool(letters and non_latin / letters < 0.05 and latin / letters > 0.5)
        previous_non_neutral_kept = keep
        if keep:
            kept.append(block)
            share = latin / letters
            if 0.5 < share < 0.7:
                borderline += 1
    warnings = [f"borderline_lang:{borderline}"] if borderline else []
    return kept, warnings


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def expand_html_table(table: Tag) -> tuple[list[list[str]], int]:
    rows = table.find_all("tr")
    cells: dict[tuple[int, int], tuple[str, bool]] = {}
    max_column = 0
    header_rows = 0
    for row_number, row in enumerate(rows):
        column = 0
        row_cells = row.find_all(["th", "td"], recursive=False)
        if row_cells and all(cell.name == "th" for cell in row_cells) and row_number == header_rows:
            header_rows += 1
        for cell in row_cells:
            while (row_number, column) in cells:
                column += 1
            text = normalize_text(cell.get_text(" ", strip=True))
            rowspan = max(1, int(cell.get("rowspan", 1) or 1))
            colspan = max(1, int(cell.get("colspan", 1) or 1))
            for row_offset in range(rowspan):
                for column_offset in range(colspan):
                    cells[(row_number + row_offset, column + column_offset)] = (text, cell.name == "th")
            column += colspan
            max_column = max(max_column, column)
    if rows and header_rows == 0:
        header_rows = 1
    grid = [
        [cells.get((row, column), ("", False))[0] for column in range(max_column)]
        for row in range(len(rows))
    ]
    return grid, header_rows


def rows_to_lines(rows: list[list[str]], header_rows: int = 1) -> list[str]:
    if not rows:
        return []
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header_rows = min(max(1, header_rows), len(padded))
    headers: list[str] = []
    for column in range(width):
        parts: list[str] = []
        for row in range(header_rows):
            value = normalize_text(padded[row][column])
            if value and value not in parts:
                parts.append(value)
        headers.append(" / ".join(parts) or f"Column {column + 1}")
    lines = []
    for row in padded[header_rows:]:
        if not any(value.strip() for value in row):
            continue
        lines.append("; ".join(f"{header}: {normalize_text(value)}" for header, value in zip(headers, row)))
    return lines


def _is_key_value_table(table: Tag) -> bool:
    """Rows like <th>Cost</th><td>Free</td> with no header row: write them as "Cost: Free"."""
    rows = [row.find_all(["th", "td"], recursive=False) for row in table.find_all("tr")]
    return bool(rows) and all(cells and cells[0].name == "th" and any(cell.name == "td" for cell in cells) for cells in rows)


def html_blocks(content: Tag) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    handled: set[int] = set()
    for element in content.descendants:
        if not isinstance(element, Tag):
            continue
        if any(id(parent) in handled for parent in element.parents if isinstance(parent, Tag)):
            continue
        if element.name == "table":
            grid, header_rows = expand_html_table(element)
            if _is_key_value_table(element):
                lines = [f"{row[0].rstrip(': ')}: {'; '.join(value for value in row[1:] if value)}" for row in grid if row and row[0]]
            else:
                lines = rows_to_lines(grid, header_rows)
            blocks.extend(TextBlock(line, "table_row") for line in lines)
            handled.add(id(element))
            continue
        if element.name in BLOCK_TAGS:
            text = normalize_text(element.get_text(" ", strip=True))
            if text:
                if element.name.startswith("h") or element.name in {"dt", "dd"}:
                    kind = "heading" if element.name.startswith("h") or element.name == "dt" else "paragraph"
                else:
                    kind = "list_item" if element.name == "li" else "paragraph"
                blocks.append(TextBlock(text, kind))
            handled.add(id(element))
            continue
        if element.name == "div":
            parts = []
            for child in element.descendants:
                if not isinstance(child, NavigableString):
                    continue
                ancestors = []
                parent = child.parent
                while parent is not None and parent is not element:
                    ancestors.append(parent)
                    parent = parent.parent
                if not any(parent.name in BLOCK_TAGS | {"div", "table"} for parent in ancestors):
                    parts.append(str(child))
            direct = normalize_text(" ".join(parts))
            if direct:
                blocks.append(TextBlock(direct, "paragraph"))
    return blocks


def _select_content(soup: BeautifulSoup, config: SiteConfig, url: str) -> Tag | None:
    parsed = urlsplit(url)
    if config.name == "seoul":
        selector = (
            ".content_body .rhymix_content.xe_content"
            if re.match(r"^/(?:notice|sub4_01|Forms)/\d+/?$", parsed.path)
            else "#content .content_inner"  # static pages stack several xe_content widgets (title, body)
        )
        return soup.select_one(selector) or soup.select_one("#content .rhymix_content.xe_content")
    if config.name == "erica":
        return soup.select_one("#bo_v_con") or soup.select_one(".sub-cnt > section")
    return soup.select_one(config.content_selector)


def _english_title(title: str) -> tuple[str, list[str]]:
    title = normalize_text(title)
    if not any(is_hangul_cjk(char) for char in title):
        return title, []
    runs = re.split(r"[\u1100-\u11ff\u3130-\u318f\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\u3040-\u30ff]+", title)
    candidates = [run.strip(" []()|-\t") for run in runs]
    candidates = [run for run in candidates if any(is_latin(char) for char in run)]
    if candidates:
        return max(candidates, key=lambda run: sum(is_latin(char) for char in run)), []
    return title, ["title_not_english"]


def extract_title(soup: BeautifulSoup, config: SiteConfig, url: str) -> tuple[str, list[str]]:
    if config.name == "seoul":
        header = soup.select_one(".content_header")
        if header:
            clone = BeautifulSoup(str(header), "html.parser")
            for metadata in clone.select(".content_info, .document_info, ul, dl"):
                metadata.decompose()
            raw = clone.get_text(" ", strip=True)
            raw = re.split(r"\s+(?:글쓴이|날짜|조회 수)\s*:", raw, maxsplit=1)[0]
        else:
            raw = soup.title.get_text(" ", strip=True) if soup.title else ""
            raw = re.sub(r"^한양대 국제처\s*-\s*", "", raw)
    else:
        header = soup.select_one("#bo_v header")
        if header:
            raw = header.get_text(" ", strip=True)
        else:
            subtitle = soup.select_one(".sub-cnt .sub-info")
            if subtitle:
                heading = subtitle.select_one("h1, h2, h3, h4, h5, h6")
                raw = heading.get_text(" ", strip=True) if heading else subtitle.get_text(" ", strip=True)
            else:
                heading = soup.select_one(".sub-cnt h1, .sub-cnt h2, .sub-cnt h3")
                raw = heading.get_text(" ", strip=True) if heading else ""
    return _english_title(raw)


def _iso_date(match: re.Match[str]) -> str:
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def extract_dates(soup: BeautifulSoup, config: SiteConfig, title: str, blocks: list[TextBlock]) -> tuple[str | None, str | None]:
    post_date = None
    if config.name == "seoul":
        header = soup.select_one(".content_header")
        match = re.search(r"날짜\s*:\s*(20\d{2})\.(\d{1,2})\.(\d{1,2})", header.get_text(" ", strip=True) if header else "")
        if match:
            post_date = _iso_date(match)
    elif config.name == "erica":
        info = soup.select_one("#bo_v_info")
        match = re.search(r"Date\s*:\s*(20\d{2})-(\d{1,2})-(\d{1,2})", info.get_text(" ", strip=True) if info else "")
        if match:
            post_date = _iso_date(match)

    effective_text = "\n".join([title, *(block.text for block in blocks)])
    match = re.search(
        r"(?:UPDATED\s*:|effective(?:\s+date)?\s*:?|applied\s*:?|from\s+|as\s+of\s+)\s*"
        r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})",
        effective_text,
        re.IGNORECASE,
    )
    return post_date, _iso_date(match) if match else None


def mask_email(text: str) -> str:
    return EMAIL_RE.sub("[email]", text)


def attachment_filename_allowed(filename: str) -> bool:
    lowered = filename.lower()
    if any(marker in lowered for marker in ("(kor)", "(korean)")):
        return False
    if any(marker in filename for marker in ("(국문)", "中文", "(중문)")):
        return False
    has_non_latin = any(is_hangul_cjk(char) for char in filename)
    return not has_non_latin or "(영문)" in filename or "(english)" in lowered


def discover_attachments(raw: bytes, page_url: str, site: str | SiteConfig) -> list[dict[str, str]]:
    config = get_site(site) if isinstance(site, str) else site
    soup = BeautifulSoup(raw, "html.parser")
    # gnuboard lists files in #bo_v_file, outside the #bo_v_con body
    content = soup.select_one("#bo_v") if config.name == "erica" else _select_content(soup, config, page_url)
    if not content:
        return []
    needle = "procFileDownload" if config.name == "seoul" else "download.php"
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in content.select(f'a[href*="{needle}"]'):
        filename = normalize_text(link.get_text(" ", strip=True)) or Path(urlsplit(link.get("href", "")).path).name
        if not attachment_filename_allowed(filename):
            continue
        url = urljoin(config.base_url, link.get("href", ""))
        if not config.is_allowed(url):
            continue
        uri = canonical_uri(url)
        if uri not in seen:
            found.append({"url": url, "canonical_uri": uri, "filename": filename})
            seen.add(uri)
    return found


def _docx_blocks(data: bytes) -> list[TextBlock]:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(BytesIO(data)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    blocks: list[TextBlock] = []
    body = root.find(f"{namespace}body")
    if body is None:
        return blocks
    for child in body:
        if child.tag == f"{namespace}p":
            text = normalize_text("".join(node.text or "" for node in child.iter(f"{namespace}t")))
            if text:
                blocks.append(TextBlock(text, "attachment"))
        elif child.tag == f"{namespace}tbl":
            rows = []
            for row in child.findall(f"{namespace}tr"):
                values = []
                for cell in row.findall(f"{namespace}tc"):
                    values.append(normalize_text(" ".join(node.text or "" for node in cell.iter(f"{namespace}t"))))
                rows.append(values)
            blocks.extend(TextBlock(line, "attachment") for line in rows_to_lines(rows))
    return blocks


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [normalize_text("".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))) for item in root]


def _xlsx_sheet_names(archive: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/workbook.xml"))
    return [sheet.attrib.get("name", "Sheet") for sheet in root.iter() if sheet.tag.endswith("}sheet")]


def _column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    value = 0
    for char in letters.group(0) if letters else "A":
        value = value * 26 + ord(char) - ord("A") + 1
    return value - 1


def _xlsx_blocks(data: bytes) -> list[TextBlock]:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        shared = _xlsx_shared_strings(archive)
        names = _xlsx_sheet_names(archive)
        sheets = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)),
            key=lambda name: int(re.search(r"\d+", Path(name).stem).group()),
        )
        blocks: list[TextBlock] = []
        for index, sheet_path in enumerate(sheets):
            root = ET.fromstring(archive.read(sheet_path))
            rows: list[list[str]] = []
            for row in (node for node in root.iter() if node.tag.endswith("}row")):
                values: dict[int, str] = {}
                for cell in (node for node in row if node.tag.endswith("}c")):
                    column = _column_number(cell.attrib.get("r", "A1"))
                    value_node = next((node for node in cell.iter() if node.tag.endswith("}v")), None)
                    inline = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                    raw_value = value_node.text if value_node is not None else inline
                    if cell.attrib.get("t") == "s" and raw_value:
                        raw_value = shared[int(raw_value)]
                    values[column] = normalize_text(raw_value or "")
                if values:
                    rows.append([values.get(column, "") for column in range(max(values) + 1)])
            while rows and not any(rows[0]):
                rows.pop(0)
            if rows:
                sheet_name = names[index] if index < len(names) else f"Sheet {index + 1}"
                blocks.append(TextBlock(f"Sheet: {sheet_name}", "attachment"))
                blocks.extend(TextBlock(line, "attachment") for line in rows_to_lines(rows))
        return blocks


def extract_attachment(data: bytes, filename: str, content_type: str = "") -> tuple[list[TextBlock], list[str]]:
    extension = Path(filename).suffix.lower()
    try:
        if extension == ".pdf" or content_type.split(";", 1)[0] == "application/pdf":
            reader = PdfReader(BytesIO(data))
            blocks = [
                TextBlock(normalize_text(line), "attachment")
                for page in reader.pages
                for line in (page.extract_text() or "").splitlines()
                if normalize_text(line)
            ]
            return (blocks, []) if blocks else ([], ["no_text_layer"])
        if extension == ".docx":
            return _docx_blocks(data), []
        if extension == ".xlsx":
            return _xlsx_blocks(data), []
    except Exception as exc:  # outside files: any parse failure becomes a warning, never a crashed crawl
        return [], [f"attachment_parse_error:{extension or 'unknown'}:{type(exc).__name__}"]
    return [], [f"unsupported_attachment:{extension or 'unknown'}"]


def _attachment_key(uri: str, filename: str) -> str:
    values = parse_qs(urlsplit(uri).query).get("file_srl")
    return values[0] if values else filename


def _coerce_attachment(value: AttachmentInput | dict[str, object]) -> AttachmentInput:
    if isinstance(value, AttachmentInput):
        return value
    return AttachmentInput(
        data=value["data"],  # type: ignore[arg-type]
        filename=str(value.get("filename", "attachment")),
        content_type=str(value.get("content_type", "")),
        canonical_uri=str(value.get("canonical_uri", "")),
        sha256=str(value.get("sha256", "")),
    )


def extract_document(
    raw: bytes,
    url: str,
    site: str | SiteConfig,
    attachments: list[AttachmentInput | dict[str, object]] | None = None,
    source_sha256: str | None = None,
) -> dict[str, object] | None:
    config = get_site(site) if isinstance(site, str) else site
    soup = BeautifulSoup(raw, "html.parser")
    title, title_warnings = extract_title(soup, config, url)
    working = BeautifulSoup(raw, "html.parser")
    for selector in config.drop_selectors:
        for node in working.select(selector):
            node.decompose()
    for node in working(["script", "style", "noscript"]):
        node.decompose()  # e.g. the Seoul partner table is built by JavaScript; its source is not text
    content = _select_content(working, config, url)
    if content is None:
        return None
    attachment_selector = 'a[href*="procFileDownload"], a[href*="download.php"]'
    for link in content.select(attachment_selector):
        link.decompose()
    page_blocks = html_blocks(content)
    post_date, effective_date = extract_dates(soup, config, title, page_blocks)
    kept_page, page_warnings = filter_english_blocks(page_blocks)

    all_raw_text = [block.text for block in page_blocks]
    attachment_records: list[dict[str, object]] = []
    kept_attachments: list[tuple[AttachmentInput, list[TextBlock]]] = []
    warnings = [*title_warnings, *page_warnings]
    for value in attachments or []:
        attachment = _coerce_attachment(value)
        blocks, attachment_warnings = extract_attachment(attachment.data, attachment.filename, attachment.content_type)
        all_raw_text.extend(block.text for block in blocks)
        kept, language_warnings = filter_english_blocks(blocks)
        combined_warnings = [*attachment_warnings, *language_warnings]
        filename = mask_email(attachment.filename)
        uri = attachment.canonical_uri
        attachment_records.append({
            "canonical_uri": uri,
            "filename": filename,
            "content_type": attachment.content_type,
            "sha256": attachment.sha256 or sha256(attachment.data).hexdigest(),
            "lang_coverage": language_counts([block.text for block in blocks]),
            "warnings": combined_warnings,
        })
        warnings.extend(combined_warnings)
        if kept:
            kept_attachments.append((attachment, kept))

    coverage = language_counts(all_raw_text)
    kept_blocks = [*kept_page, *(block for _, blocks in kept_attachments for block in blocks)]
    if sum(is_latin(char) for block in kept_blocks for char in block.text) < MIN_ENGLISH_LETTERS:
        return None

    text = ""
    spans: list[dict[str, object]] = []
    for block in kept_page:
        if text:
            text += "\n"
        start = len(text)
        text += mask_email(block.text)
        spans.append({"char_start": start, "char_end": len(text), "kind": block.kind, "source": "page"})
    for attachment, blocks in kept_attachments:
        filename = mask_email(attachment.filename)
        prefix = f"\n\nAttachment: {filename}\n" if text else f"Attachment: {filename}\n"
        start = len(text)
        text += prefix + "\n".join(mask_email(block.text) for block in blocks)
        source = f"attachment:{_attachment_key(attachment.canonical_uri, filename)}"
        spans.append({"char_start": start, "char_end": len(text), "kind": "attachment", "source": source})

    parsed = urlsplit(canonical_uri(url))
    query = parse_qs(parsed.query)
    path_parts = [part for part in parsed.path.split("/") if part]
    board: str | None = None
    post_id: str | None = None
    if config.name == "seoul" and len(path_parts) >= 2 and path_parts[0] in {"notice", "sub4_01", "Forms"}:
        board, post_id = path_parts[0], path_parts[1]
    elif config.name == "erica" and "bo_table" in query:
        board = query["bo_table"][0]
        post_id = query.get("wr_id", [None])[0]

    source_uri = canonical_uri(url)
    return {
        "doc_id": doc_id_for_url(source_uri),
        "source_uri": source_uri,
        "site": config.name,
        "campus": config.campus,
        "board": board,
        "post_id": post_id,
        "title": mask_email(title),
        "post_date": post_date,
        "effective_date": effective_date,
        "text": text,
        "spans": spans,
        "attachments": attachment_records,
        "lang_coverage": coverage,
        "warnings": sorted(set(warnings)),
        "parser_id": config.parser_id,
        "source_sha256": source_sha256 or sha256(raw).hexdigest(),
        "version_family_id": None,
        "superseded_by": None,
        "aliases": [],
    }


def discover_sitemap(raw: bytes, site: str | SiteConfig = "seoul") -> list[str]:
    config = get_site(site) if isinstance(site, str) else site
    root = ET.fromstring(raw)
    urls = []
    seen = set()
    for node in root.iter():
        if node.tag.endswith("}loc") or node.tag == "loc":
            url = normalize_text(node.text or "")
            uri = canonical_uri(url)
            if url and config.is_allowed(url) and uri not in seen:
                urls.append(url)
                seen.add(uri)
    return urls


def discover_erica_menu(raw: bytes) -> list[str]:
    soup = BeautifulSoup(raw, "html.parser")
    urls: list[str] = []
    seen = set()
    for link in soup.select("a[href]"):
        url = urljoin(SITES["erica"].base_url, link.get("href", ""))
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        is_menu = bool(re.match(r"^/eng/s[123]/.+\.php$", parsed.path))
        is_board = (
            parsed.path == "/bbs/board.php"
            and query.get("bo_table", [""])[0] in ERICA_BOARD_NAMES
            and "wr_id" not in query
        )
        uri = canonical_uri(url)
        if (is_menu or is_board) and SITES["erica"].is_allowed(url) and uri not in seen:
            urls.append(url)
            seen.add(uri)
    return urls


def discover_board_posts(raw: bytes, listing_url: str) -> list[str]:
    soup = BeautifulSoup(raw, "html.parser")
    urls: list[str] = []
    seen = set()
    for link in soup.select('#fboardlist tbody tr a[href*="wr_id"]'):
        url = urljoin(listing_url, link.get("href", ""))
        uri = canonical_uri(url)
        if uri not in seen and SITES["erica"].is_allowed(url):
            urls.append(uri)
            seen.add(uri)
    return urls

