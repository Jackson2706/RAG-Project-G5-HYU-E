from __future__ import annotations

import json

from labeling import _snapshot
from labeling.topics import generate_topics


def _row(doc_id, title, source_uri, parts, attachments=None):
    text = "\n".join(piece for _, piece in parts)
    spans, offset = [], 0
    for kind, piece in parts:
        spans.append({"kind": kind, "char_start": offset, "char_end": offset + len(piece), "source": "page"})
        offset += len(piece) + 1
    return {
        "aliases": [],
        "attachments": attachments or [],
        "board": None,
        "campus": "seoul",
        "doc_id": doc_id,
        "effective_date": None,
        "lang_coverage": {"en_letters": 100, "ratio": 1.0, "total_letters": 100},
        "parser_id": "synthetic-v1",
        "post_date": "2026-11-01",
        "post_id": None,
        "site": "seoul",
        "source_sha256": "0" * 64,
        "source_uri": source_uri,
        "spans": spans,
        "superseded_by": None,
        "text": text,
        "title": title,
        "version_family_id": None,
        "warnings": [],
    }


def test_topics_use_only_titles_and_english_headings(tmp_path, monkeypatch):
    bodies = [
        "SECRET HOUSING BODY",
        "SECRET VISA BODY",
        "한국어 비밀 본문",
    ]
    long_heading = "Housing " + "x" * 130
    rows = [
        _row(
            "housing",
            "Housing https://example.test/path?token=secret",
            "https://example.test/housing",
            [("heading", long_heading), ("heading", long_heading), ("paragraph", bodies[0])],
        ),
        _row(
            "visa",
            "Visa forms",
            "https://example.test/board.php?id=7",
            [("heading", "Contact adviser@example.org"), ("attachment", f"Attachment: 영문 안내.pdf\n{bodies[1]}")],
            [{"filename": "visa-guide.pdf"}],
        ),
        _row(
            "korean",
            "Korean notice",
            "https://example.test/notice.hwp",
            [("heading", "한국어 안내"), ("paragraph", bodies[2])],
        ),
    ]
    folder = tmp_path / "snapshots" / "synthetic"
    folder.mkdir(parents=True)
    (folder / "documents.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(_snapshot, "snapshot_dir", lambda _: folder)

    output = tmp_path / "topics.jsonl"
    topics = generate_topics("synthetic", output)
    serialized = output.read_text(encoding="utf-8")

    assert len(topics) == 3
    assert all(body not in serialized for body in bodies)
    assert topics[0]["headings"] == [long_heading[:120]]
    assert "?token=secret" not in topics[0]["title"]
    assert topics[1]["headings"] == ["Contact [email]"]
    assert topics[1]["file_type"] == "pdf"
    assert topics[2]["headings"] == []
    assert topics[2]["file_type"] == "hwp"
    assert topics[2]["korean_only"] is True
