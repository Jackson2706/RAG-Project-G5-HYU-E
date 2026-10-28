"""Retrieval primitives: metadata filters, dense search, BM25 and rank fusion."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from qdrant_client import models

from app.ingestion.metadata import AUDIENCE_PARENTS, STOPWORDS
from app.ingestion.pipeline import chunk_payload
from app.models.documents import Chunk
from app.models.pipeline import Candidate, MetadataFilterSpec

TOKEN = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")

# --------------------------------------------------------------------------- metadata filter


def _field_conditions(spec: MetadataFilterSpec) -> list[tuple[str, list[str]]]:
    """(payload field, accepted values) pairs; documents match if their field holds any accepted value."""
    out = []
    if spec.campus:
        out.append(("campus", [spec.campus] + (["ALL"] if spec.include_university_wide else [])))
    if spec.audience:
        broader = [p for a in spec.audience for p in AUDIENCE_PARENTS.get(a, [])]
        out.append(("audience", list(dict.fromkeys([*spec.audience, *broader, "all"]))))
    for name in ("document_type", "academic_year", "language"):
        value = getattr(spec, name)
        if value:
            out.append((name, [value]))
    return out


def build_qdrant_filter(spec: MetadataFilterSpec | None) -> models.Filter | None:
    """Compile the validated spec to a native Qdrant filter (no string interpolation).

    Each constrained field becomes one `must` clause: field ∈ accepted values, OR
    (when include_unknown) the field is null/empty — unknown is not ineligible.
    """
    if spec is None or spec.is_empty():
        return None
    must: list[models.Condition] = []
    for field_name, values in _field_conditions(spec):
        should: list[models.Condition] = [models.FieldCondition(key=field_name, match=models.MatchAny(any=values))]
        if spec.include_unknown:
            should += [models.IsNullCondition(is_null=models.PayloadField(key=field_name)),
                       models.IsEmptyCondition(is_empty=models.PayloadField(key=field_name))]  # fmt: skip
        must.append(models.Filter(should=should))
    return models.Filter(must=must)


def matches_filter(payload: dict[str, Any], spec: MetadataFilterSpec | None) -> bool:
    """Same semantics as build_qdrant_filter, evaluated in Python (used for BM25 candidates)."""
    if spec is None or spec.is_empty():
        return True
    for field_name, values in _field_conditions(spec):
        value = payload.get(field_name)
        if value is None or value == []:
            if spec.include_unknown:
                continue
            return False
        held = value if isinstance(value, list) else [value]
        if not set(held) & set(values):
            return False
    return True


def describe_filter(f: models.Filter | None) -> dict[str, Any] | None:
    return f.model_dump(exclude_none=True) if f else None


# --------------------------------------------------------------------------- BM25


def bm25_tokens(text: str, remove_stopwords: bool) -> list[str]:
    tokens = TOKEN.findall(text.lower())
    return [t for t in tokens if t not in STOPWORDS] if remove_stopwords else tokens


class BM25Index:
    """Okapi BM25 over the chunks of one index revision.

    score(q, d) = Σ_t IDF(t) · tf(t,d)·(k1+1) / (tf(t,d) + k1·(1 − b + b·|d|/avgdl))
    IDF(t) = ln(1 + (N − df(t) + 0.5) / (df(t) + 0.5))
    """

    def __init__(self, chunks: list[Chunk], remove_stopwords: bool, revision_id: str) -> None:
        self.revision_id = revision_id
        self.remove_stopwords = remove_stopwords
        self.chunks = chunks
        self.docs = [Counter(bm25_tokens(c.embedding_text, remove_stopwords)) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avgdl = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, top_k: int, k1: float, b: float, spec: MetadataFilterSpec | None) -> tuple[list[tuple[Chunk, float]], list[str]]:
        terms = [t for t in dict.fromkeys(bm25_tokens(query, self.remove_stopwords))]
        scored = []
        for chunk, tf, length in zip(self.chunks, self.docs, self.lengths, strict=True):
            score = 0.0
            for t in terms:
                f = tf.get(t)
                if f:
                    score += self.idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * length / (self.avgdl or 1)))
            if score > 0 and matches_filter(chunk_payload(chunk), spec):
                scored.append((chunk, score))
        scored.sort(key=lambda cs: (-cs[1], cs[0].chunk_id))
        return scored[:top_k], terms


# --------------------------------------------------------------------------- fusion


def fuse(dense: list[Candidate], lexical: list[Candidate], method: str, params: dict[str, Any]) -> list[Candidate]:
    """Merge candidate lists. Each candidate keeps its per-retriever scores and ranks."""
    if method == "none":
        only = dense or lexical
        return [c.model_copy(update={"fused_rank": i + 1}) for i, c in enumerate(only)]
    merged: dict[str, Candidate] = {}
    for c in dense:
        merged[c.chunk_id] = c.model_copy()
    for c in lexical:
        if c.chunk_id in merged:
            merged[c.chunk_id].lexical_score, merged[c.chunk_id].lexical_rank = c.lexical_score, c.lexical_rank
        else:
            merged[c.chunk_id] = c.model_copy()
    if method == "rrf":
        k = params["rrf_k"]
        for c in merged.values():
            c.fused_score = sum(1.0 / (k + r) for r in (c.dense_rank, c.lexical_rank) if r is not None)
    elif method == "weighted":
        w = params["dense_weight"]
        dn = _minmax({c.chunk_id: c.dense_score for c in dense})
        ln = _minmax({c.chunk_id: c.lexical_score for c in lexical})
        for c in merged.values():
            c.fused_score = w * dn.get(c.chunk_id, 0.0) + (1 - w) * ln.get(c.chunk_id, 0.0)
    else:
        raise ValueError(f"fusion method '{method}' is not implemented")
    ranked = sorted(merged.values(), key=lambda c: (-(c.fused_score or 0.0), c.dense_rank or 10**6, c.lexical_rank or 10**6, c.chunk_id))
    out = ranked[: params["candidate_limit"]]
    for i, c in enumerate(out):
        c.fused_score = round(c.fused_score or 0.0, 6)
        c.fused_rank = i + 1
    return out


def _minmax(scores: dict[str, float | None]) -> dict[str, float]:
    values = {k: v for k, v in scores.items() if v is not None}
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    return {k: 1.0 if hi == lo else (v - lo) / (hi - lo) for k, v in values.items()}
