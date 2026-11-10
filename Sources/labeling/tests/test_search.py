from __future__ import annotations

import json

import pytest

from app.rag.snapshot import snapshot_dir
from labeling import _snapshot
from labeling.search import bm25_scores, search_snapshot, snapshot_units


def _row(doc_id, campus, parts):
    text = "\n".join(piece for _, piece in parts)
    spans, offset = [], 0
    for kind, piece in parts:
        spans.append({"kind": kind, "char_start": offset, "char_end": offset + len(piece)})
        offset += len(piece) + 1
    return {
        "doc_id": doc_id,
        "source_uri": f"https://example.test/{doc_id}",
        "title": doc_id,
        "campus": campus,
        "text": text,
        "spans": spans,
        "post_date": None,
        "superseded_by": None,
    }


def test_bm25_matches_hand_computed_score():
    """For lengths 2 and 1, avgdl=1.5 and df=2; compare the formula in bm25_scores."""
    scores = bm25_scores("visa", ["visa visa", "visa"])
    idf = __import__("math").log(1 + 0.5 / 2.5)
    expected = idf * (2 * 2.5) / (2 + 1.5 * (0.25 + 0.75 * 2 / 1.5))
    assert scores[0] == pytest.approx(expected)


def test_search_ranks_exact_snapshot_span_first(tmp_path, monkeypatch):
    rows = [
        _row("housing", "seoul", [("heading", "Housing"), ("paragraph", "Dormitory applications open soon.")]),
        _row(
            "visa",
            "erica",
            [("heading", "Registration"), ("paragraph", "Alien registration needs a passport photo.")],
        ),
        _row("insurance", "erica", [("heading", "Insurance"), ("paragraph", "Premium notices are online.")]),
    ]
    folder = tmp_path / "snapshots" / "synthetic"
    folder.mkdir(parents=True)
    (folder / "documents.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(_snapshot, "snapshot_dir", lambda _: folder)

    result = search_snapshot("alien passport photo", "synthetic", k=3, campus="erica")[0].unit
    expected = rows[1]["spans"][1]
    assert result.doc_id == "visa"
    assert (result.char_start, result.char_end) == (expected["char_start"], expected["char_end"])
    assert rows[1]["text"][result.char_start : result.char_end] == result.text

    section = next(unit for unit in snapshot_units(rows) if unit.doc_id == "visa" and unit.kind == "section")
    assert section.char_start == 0 and section.char_end == len(rows[1]["text"])
    assert rows[1]["text"][section.char_start : section.char_end] == section.text


def test_real_snapshot_search_smoke():
    snapshot_id = "hyu-20261110-97dc1269"
    if not (snapshot_dir(snapshot_id) / "documents.jsonl").exists():
        pytest.skip("committed HYU snapshot is absent")
    assert search_snapshot("alien registration", snapshot_id, k=5)
