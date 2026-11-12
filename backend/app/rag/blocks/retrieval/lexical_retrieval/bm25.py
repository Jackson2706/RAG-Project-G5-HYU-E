"""IMPLEMENTED — Okapi BM25 keyword ranking over the indexed chunks."""

from __future__ import annotations

import math
import re
import time
from collections import Counter
from dataclasses import dataclass

import numpy as np

from app.rag.blocks.retrieval.lexical_retrieval.base import BaseLexicalRetriever
from app.rag.schemas import Candidate, RetrievalFilter, RetrievalResult

# Lucene's English stop words (the words Elasticsearch's "english" analyzer drops). No stemming.
STOPWORDS = frozenset("a an and are as at be but by for if in into is it no not of on or such that the their then there "
                      "these they this to was will with".split())  # fmt: skip
WORD = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    """Lowercase words (letters/digits), without stop words. "Add/drop period?" → ["add", "drop", "period"]."""
    return [w for w in WORD.findall(text.lower()) if w not in STOPWORDS]


@dataclass
class LexicalIndex:
    """An inverted index of one vector-index revision: for each word, which chunks contain it how often."""

    chunk_ids: list[str]
    doc_ids: list[str]
    metadata: list[dict]  # the chunk's document metadata (for prefiltering)
    lengths: np.ndarray  # words per chunk
    postings: dict[str, tuple[np.ndarray, np.ndarray]]  # word → (chunk positions, term frequencies)
    build_ms: float


_CACHE: dict[tuple, LexicalIndex] = {}


def build_lexical_index(db) -> LexicalIndex:
    """Read every chunk from MongoDB once. The text is "section heading + chunk text" — exactly what
    dense retrieval embeds — so both retrievers rank the same units."""
    start = time.perf_counter()
    documents = {d["doc_id"]: d.get("metadata", {}) for d in db.documents.find({}, {"_id": 0, "doc_id": 1, "metadata": 1})}
    chunk_ids, doc_ids, metadata, lengths, postings = [], [], [], [], {}
    for position, c in enumerate(db.chunks.find({}, {"_id": 0, "chunk_id": 1, "doc_id": 1, "section": 1, "text": 1})):
        words = tokenize(f"{c['section']}\n{c['text']}" if c.get("section") else c["text"])
        chunk_ids.append(c["chunk_id"])
        doc_ids.append(c["doc_id"])
        metadata.append(documents.get(c["doc_id"], {}))
        lengths.append(len(words))
        for word, count in Counter(words).items():
            postings.setdefault(word, ([], []))
            postings[word][0].append(position)
            postings[word][1].append(count)
    arrays = {w: (np.array(p, dtype=np.int64), np.array(f, dtype=np.float64)) for w, (p, f) in postings.items()}
    return LexicalIndex(chunk_ids, doc_ids, metadata, np.array(lengths, dtype=np.float64), arrays,
                        round((time.perf_counter() - start) * 1000, 1))  # fmt: skip


def get_lexical_index(db) -> LexicalIndex:
    """The cached index for this index revision; rebuilt when the index was re-built (manifest time or chunk count)."""
    manifest = db.get_manifest() or {}
    key = (db.mongo.name, db.collection, manifest.get("built_at"), db.chunks.estimated_document_count())
    if key not in _CACHE:
        _CACHE.clear()  # keep only one index in memory
        _CACHE[key] = build_lexical_index(db)
    return _CACHE[key]


def bm25_scores(index: LexicalIndex, query_words: list[str], k1: float, b: float) -> np.ndarray:
    """BM25 score of every chunk (0 = no query word):

        score = Σ over query words w:  idf(w) · tf·(k1+1) / (tf + k1·(1 − b + b·len/avg_len))
        idf(w) = ln(1 + (N − df + 0.5) / (df + 0.5))      (Lucene's always-positive idf)
    """
    n = len(index.chunk_ids)
    scores = np.zeros(n)
    if n == 0:
        return scores
    norm = k1 * (1 - b + b * index.lengths / (index.lengths.mean() or 1.0))
    for word in set(query_words):  # each distinct query word counts once
        if word not in index.postings:
            continue
        positions, tf = index.postings[word]
        idf = math.log(1 + (n - len(positions) + 0.5) / (len(positions) + 0.5))
        scores[positions] += idf * tf * (k1 + 1) / (tf + norm[positions])
    return scores


class BM25Retriever(BaseLexicalRetriever):
    """Hyperparameters: top_k, k1 (term-frequency saturation), b (length normalization).

    BM25 scores are NOT cosine similarities: they are unbounded and only comparable within one query.
    A prefilter predicate is applied while ranking: ineligible chunks never get a rank.
    """

    async def retrieve(self, query: str, prefilter: RetrievalFilter | None = None) -> RetrievalResult:
        index = get_lexical_index(self.services.db)
        if not index.chunk_ids:
            raise RuntimeError("No documents are indexed yet. Run: python scripts/ingest.py --path data/filter_ready")
        start = time.perf_counter()
        words = tokenize(query)
        scores = bm25_scores(index, words, self.params["k1"], self.params["b"])
        eligible = scores > 0  # a chunk must contain at least one query word
        if prefilter:
            eligible &= np.array([prefilter.matches(m) for m in index.metadata])
        positions = np.flatnonzero(eligible)
        top = positions[np.lexsort((positions, -scores[positions]))][: self.params["top_k"]]  # ties: index order
        candidates = [Candidate(rank=r + 1, chunk_id=index.chunk_ids[i], doc_id=index.doc_ids[i], score=round(float(scores[i]), 4),
                                scores={"bm25": round(float(scores[i]), 4)}) for r, i in enumerate(top)]  # fmt: skip
        details = {"score": "BM25 (unbounded; not a cosine similarity)", "query_words": words, "matching_chunks": int(eligible.sum()),
                   "indexed_chunks": len(index.chunk_ids), "index_build_ms": index.build_ms,
                   "search_ms": round((time.perf_counter() - start) * 1000, 2)}  # fmt: skip
        return RetrievalResult(candidates=candidates, applied_filter=prefilter, details=details)
