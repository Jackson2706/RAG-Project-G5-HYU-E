"""Download and load the ConditionalQA eligibility-question dataset."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from app.config import DATA_DIR
from app.rag.schemas import ParsedDocument, Section
from evaluation.beir import write_source_md

COMMIT = "77bd295952daf415548b3244db10880d3d55cfe0"
BASE_URL = f"https://raw.githubusercontent.com/haitian-sun/ConditionalQA/{COMMIT}/v1_0"
FILENAMES = ("train.json", "dev.json", "test_no_answer.json", "documents.json")
URLS = {name: f"{BASE_URL}/{name}" for name in FILENAMES}
FOLDER = DATA_DIR / "benchmarks" / "conditionalqa"
USER_AGENT = "hyu-compass-benchmarks/1.0"
LOGGER = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch(url: str, part: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, open(part, "wb") as output:
            shutil.copyfileobj(response, output)
    except Exception:
        part.unlink(missing_ok=True)
        raise


def download() -> dict:
    """Download pinned files, recording first-seen hashes and enforcing them on later calls."""
    FOLDER.mkdir(parents=True, exist_ok=True)
    source_path = FOLDER / "SOURCE.json"
    source = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else None
    recorded = source.get("files", {}) if source else {}
    files = {}

    for name, url in URLS.items():
        target = FOLDER / name
        expected = recorded.get(name, {}).get("sha256")
        if target.exists() and expected:
            actual = _sha256(target)
            if actual != expected:
                raise RuntimeError(f"ConditionalQA {name} checksum {actual} does not match recorded {expected}")
        else:
            part = FOLDER / f"{name}.part"
            print(f"Downloading {url} …", flush=True)
            _fetch(url, part)
            actual = _sha256(part)
            if expected and actual != expected:
                part.unlink(missing_ok=True)
                raise RuntimeError(f"ConditionalQA {name} checksum {actual} does not match recorded {expected}")
            part.replace(target)
        files[name] = {
            "sha256": actual,
            "verified": False,
            "note": "pinned commit, sha256 recorded on first download",
        }

    if source is None:
        source = {
            "dataset": "conditionalqa",
            "urls": URLS,
            "license": "BSD 2-Clause",
            "license_note": "This dataset should ONLY be used for NLP research purpose.",
            "downloaded_at": datetime.now(UTC).isoformat(),
            "splits": ["train", "dev", "test"],
            "contents": "This folder holds ConditionalQA questions and the published source documents as raw HTML elements.",
        }
    source["files"] = files
    source_path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    write_source_md(FOLDER, source)
    return source


def load_questions(split: str) -> list[dict]:
    if split not in ("train", "dev", "test"):
        raise ValueError("ConditionalQA split must be 'train', 'dev', or 'test'")
    filename = "test_no_answer.json" if split == "test" else f"{split}.json"
    rows = json.loads((FOLDER / filename).read_text(encoding="utf-8"))
    if split == "test":
        LOGGER.info("ConditionalQA test labels are not public; returning None for missing fields")

    questions = []
    for row in rows:
        answers = None if split == "test" else [
            {"answer": answer, "conditions": list(conditions)} for answer, conditions in row["answers"]
        ]
        questions.append({
            "id": row["id"],
            "url": row["url"],
            "scenario": row["scenario"],
            "question": row["question"],
            "not_answerable": None if split == "test" else bool(row["not_answerable"]),
            "answers": answers,
            "evidences": None if split == "test" else list(row["evidences"]),
        })
    return questions


def load_documents() -> dict[str, dict]:
    rows = json.loads((FOLDER / "documents.json").read_text(encoding="utf-8"))
    documents = {}
    for row in rows:
        url = row["url"]
        if url in documents:
            raise ValueError(f"Duplicate ConditionalQA document URL: {url}")
        documents[url] = {"title": row["title"], "contents": list(row["contents"])}
    return documents


class _ElementsParser(HTMLParser):
    """Return the text and outer tag of each top-level HTML element."""

    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str | None, str]] = []
        self._tag: str | None = None
        self._depth = 0
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if self._tag is None:
            self._tag = tag
            self._text = []
        elif tag == "br":
            self._text.append("\n")
        if tag not in self.VOID_TAGS:
            self._depth += 1
        elif self._depth == 0:
            self._finish_block()

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._depth:
            self._depth -= 1
        if self._depth == 0:
            self._finish_block()

    def handle_data(self, data: str) -> None:
        if self._tag is None:
            text = " ".join(data.split())
            if text:
                self.blocks.append((None, text))
        else:
            self._text.append(data)

    def close(self) -> None:
        super().close()
        if self._tag is not None:
            self._finish_block()

    def _finish_block(self) -> None:
        text = " ".join("".join(self._text).split())
        if text:
            self.blocks.append((self._tag, text))
        self._tag, self._depth, self._text = None, 0, []


def to_parsed_documents(docs: dict[str, dict]) -> list[ParsedDocument]:
    parsed = []
    for index, (url, doc) in enumerate(docs.items()):
        section_rows: list[dict] = []
        for raw_html in doc["contents"]:
            parser = _ElementsParser()
            parser.feed(raw_html)
            parser.close()
            for tag, text in parser.blocks:
                if tag in ("h1", "h2", "h3", "h4"):
                    section_rows.append({"heading": text, "parts": []})
                else:
                    if not section_rows:
                        section_rows.append({"heading": None, "parts": []})
                    section_rows[-1]["parts"].append(text)
        sections = [Section(heading=row["heading"], text="\n".join(row["parts"])) for row in section_rows]
        parsed.append(ParsedDocument(
            path=Path("conditionalqa") / f"{index}.html",
            source_uri="conditionalqa://" + url,
            file_type="conditionalqa",
            title=doc["title"],
            sections=sections,
        ))
    return parsed
