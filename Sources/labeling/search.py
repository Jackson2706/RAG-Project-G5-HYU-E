"""Search frozen snapshot spans for labeling evidence offsets.

Run from ``Sources/``::

    python -m labeling.search "part-time work hours" --campus erica
"""

from __future__ import annotations

import argparse
import math
import re
from collections import Counter
from dataclasses import dataclass

from labeling._snapshot import DEFAULT_SNAPSHOT_ID, load_snapshot_rows

TOKEN = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class SearchUnit:
    doc_id: str
    campus: str
    char_start: int
    char_end: int
    kind: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    unit: SearchUnit
    score: float


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def bm25_scores(query: str, texts: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Return BM25 scores using positive Robertson IDF.

    For two documents ``["visa visa", "visa"]`` and query ``"visa"``, the document lengths
    are 2 and 1, average length is 1.5, and df is 2. The first score is therefore
    ``log(1 + 0.5/2.5) * (2*2.5)/(2 + 1.5*(0.25 + 0.75*2/1.5))``.
    """
    documents = [tokenize(text) for text in texts]
    if not documents:
        return []
    query_terms = tokenize(query)
    if not query_terms:
        return [0.0] * len(documents)
    average_length = sum(map(len, documents)) / len(documents) or 1.0
    frequencies = [Counter(document) for document in documents]
    scores = [0.0] * len(documents)
    for term in query_terms:
        document_frequency = sum(term in frequency for frequency in frequencies)
        if not document_frequency:
            continue
        inverse_document_frequency = math.log(
            1 + (len(documents) - document_frequency + 0.5) / (document_frequency + 0.5)
        )
        for index, frequency in enumerate(frequencies):
            count = frequency[term]
            if not count:
                continue
            length_factor = 1 - b + b * len(documents[index]) / average_length
            scores[index] += inverse_document_frequency * count * (k1 + 1) / (count + k1 * length_factor)
    return scores


def snapshot_units(rows: list[dict], campus: str | None = None) -> list[SearchUnit]:
    units: list[SearchUnit] = []
    for row in rows:
        if campus and row["campus"] != campus:
            continue
        text = row["text"]
        spans = row["spans"]
        for span in spans:
            start, end = span["char_start"], span["char_end"]
            units.append(SearchUnit(row["doc_id"], row["campus"], start, end, span["kind"], text[start:end]))

        headings = [span for span in spans if span["kind"] == "heading"]
        for index, heading in enumerate(headings):
            start = heading["char_start"]
            end = headings[index + 1]["char_start"] if index + 1 < len(headings) else len(text)
            units.append(SearchUnit(row["doc_id"], row["campus"], start, end, "section", text[start:end]))
    return units


def search_rows(query: str, rows: list[dict], k: int = 10, campus: str | None = None) -> list[SearchResult]:
    if k < 1:
        raise ValueError("k must be at least 1")
    units = snapshot_units(rows, campus)
    scores = bm25_scores(query, [unit.text for unit in units])
    ranked = sorted(zip(units, scores, strict=True), key=lambda item: item[1], reverse=True)
    return [SearchResult(unit, score) for unit, score in ranked[:k] if score > 0]


def search_snapshot(
    query: str, snapshot_id: str = DEFAULT_SNAPSHOT_ID, k: int = 10, campus: str | None = None
) -> list[SearchResult]:
    return search_rows(query, load_snapshot_rows(snapshot_id), k, campus)


def _preview(text: str) -> str:
    return " ".join(text.split())[:200]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT_ID)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--campus", choices=("seoul", "erica"))
    args = parser.parse_args(argv)

    for rank, result in enumerate(search_snapshot(args.query, args.snapshot, args.k, args.campus), start=1):
        unit = result.unit
        print(
            f"{rank}\t{unit.doc_id}\t{unit.campus}\t{unit.char_start}-{unit.char_end}\t"
            f"{unit.kind}\t{_preview(unit.text)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
