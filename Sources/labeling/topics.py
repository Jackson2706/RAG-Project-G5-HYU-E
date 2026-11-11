"""Build the title-and-heading topic list from a frozen HYU snapshot."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from app.config import DATA_DIR
from app.rag.snapshot import is_english
from crawler.extract import TextBlock, filter_english_blocks, mask_email
from labeling import _snapshot

TOPICS_PATH = DATA_DIR / "HYU" / "labels" / "topics.jsonl"
URL = re.compile(r"https?://[^\s<>()]+")
EXTENSION = re.compile(r"\.([A-Za-z0-9]{1,8})(?:\s*\([^)]*\))?$")
WEB_EXTENSIONS = {"", "asp", "aspx", "htm", "html", "jsp", "php"}


def _without_url_queries(text: str) -> str:
    def strip_query(match: re.Match[str]) -> str:
        parts = urlsplit(match.group())
        return urlunsplit(parts._replace(query=""))

    return URL.sub(strip_query, text)


def _clean_text(text: object) -> str:
    return _without_url_queries(mask_email(str(text or ""))).strip()


def _span_text(row: dict, span: dict) -> str:
    start, end = span.get("char_start"), span.get("char_end")
    text = row.get("text", "")
    if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(text):
        return ""
    return text[start:end].strip()


def _is_english_body(text: str, kind: str) -> bool:
    kept, _ = filter_english_blocks([TextBlock(text, kind)])
    return bool(kept)


def _extension(value: str) -> str:
    path = unquote(urlsplit(value).path) if "://" in value else value
    match = EXTENSION.search(path.strip())
    return match.group(1).lower() if match else ""


def _file_type(row: dict) -> str:
    source_type = _extension(str(row.get("source_uri", "")))
    if source_type not in WEB_EXTENSIONS:
        return source_type
    for attachment in row.get("attachments", []):
        attachment_type = _extension(str(attachment.get("filename", "")))
        if attachment_type:
            return attachment_type
    return "html"


def topic_row(row: dict) -> dict:
    headings: list[str] = []
    seen: set[str] = set()
    has_english_body = False
    for span in row.get("spans", []):
        piece = _span_text(row, span)
        if span.get("kind") == "heading":
            if is_english(piece):
                heading = _clean_text(piece)[:120].rstrip()
                if heading and heading not in seen:
                    headings.append(heading)
                    seen.add(heading)
        elif _is_english_body(piece, str(span.get("kind", "paragraph"))):
            has_english_body = True

    return {
        "doc_id": row["doc_id"],
        "site": row["site"],
        "title": _clean_text(row.get("title", "")),
        "headings": headings,
        "post_date": row.get("post_date"),
        "superseded_by": row.get("superseded_by"),
        "file_type": _file_type(row),
        "korean_only": not has_english_body,
    }


def write_topics(rows: list[dict], output_path: Path) -> list[dict]:
    topics = [topic_row(row) for row in rows]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for topic in topics:
            handle.write(json.dumps(topic, ensure_ascii=False) + "\n")
    return topics


def generate_topics(snapshot_id: str, output_path: Path = TOPICS_PATH) -> list[dict]:
    return write_topics(_snapshot.load_snapshot_rows(snapshot_id), output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=_snapshot.DEFAULT_SNAPSHOT_ID)
    args = parser.parse_args(argv)
    try:
        topics = generate_topics(args.snapshot)
    except (FileNotFoundError, KeyError, json.JSONDecodeError, OSError) as error:
        print(error)
        return 1
    print(f"Wrote {len(topics)} topics to {TOPICS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
