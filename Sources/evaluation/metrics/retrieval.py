"""Ranking metrics for one query and their averages (BEIR / pytrec_eval conventions).

Conventions (the same for every compared method):
- A document is RELEVANT when its qrels grade is > 0. JUDGED = it appears in the qrels at all.
- nDCG uses the graded relevance as gain and 1/log2(rank + 1) as discount; the ideal DCG is built
  from ALL judged relevant documents of the query (also those the system missed).
- P@k divides by k, even when fewer than k documents were returned (missing ranks count as misses).
- MAP@k = (Σ over relevant documents in the top k of P@rank) / number of relevant documents.
- R_cap@k = relevant in top k / min(k, number of relevant).
- MRR@k / RR@k = 1 / rank of the first relevant document within k (0 if none).
- Hit Rate@k = 1 if at least one relevant document is in the top k.
- Hole@k = share of the top k that are NOT JUDGED for any query of the dataset (BEIR's definition;
  divides by k). Unjudged ≠ irrelevant.
- A query with no relevant document has recall, MAP, nDCG, MRR, Hit Rate and R_cap UNDEFINED (None):
  it is excluded from those averages and counted, never silently scored 0.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

DEFAULT_CUTOFFS = {"ndcg": (5, 10), "map": (100,), "recall": (5, 10, 20, 100), "precision": (5, 10), "mrr": (10,),
                   "hit": (1, 5, 10), "r_cap": (5, 10), "hole": (10,)}  # fmt: skip


def clean_ranking(ranking: Iterable[str], query_id: str | None = None, ignore_identical_ids: bool = True) -> list[str]:
    """Drop duplicate documents (keep the first) and — like BEIR — the query's own ID (ArguAna's corpus
    contains the query argument itself)."""
    seen, result = set(), []
    for doc in ranking:
        if doc in seen or (ignore_identical_ids and doc == query_id):
            continue
        seen.add(doc)
        result.append(doc)
    return result


def precision_at(ranking: list[str], relevant: set[str], k: int) -> float:
    return sum(d in relevant for d in ranking[:k]) / k


def recall_at(ranking: list[str], relevant: set[str], k: int) -> float | None:
    return sum(d in relevant for d in ranking[:k]) / len(relevant) if relevant else None


def capped_recall_at(ranking: list[str], relevant: set[str], k: int) -> float | None:
    return sum(d in relevant for d in ranking[:k]) / min(k, len(relevant)) if relevant else None


def reciprocal_rank_at(ranking: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    return next((1.0 / rank for rank, d in enumerate(ranking[:k], start=1) if d in relevant), 0.0)


def hit_at(ranking: list[str], relevant: set[str], k: int) -> float | None:
    return float(any(d in relevant for d in ranking[:k])) if relevant else None


def average_precision_at(ranking: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    hits, total = 0, 0.0
    for rank, d in enumerate(ranking[:k], start=1):
        if d in relevant:
            hits += 1
            total += hits / rank
    return total / len(relevant)


def ndcg_at(ranking: list[str], grades: dict[str, int], k: int) -> float | None:
    gains = sorted((g for g in grades.values() if g > 0), reverse=True)
    ideal = sum(g / math.log2(rank + 1) for rank, g in enumerate(gains[:k], start=1))
    if ideal == 0:
        return None
    dcg = sum(max(grades.get(d, 0), 0) / math.log2(rank + 1) for rank, d in enumerate(ranking[:k], start=1))
    return dcg / ideal


def hole_at(ranking: list[str], judged: set[str], k: int) -> float:
    return sum(d not in judged for d in ranking[:k]) / k


def query_metrics(ranking: list[str], grades: dict[str, int], judged_corpus: set[str], cutoffs: dict = DEFAULT_CUTOFFS) -> dict[str, float | None]:
    """All metrics for one query. `grades` = qrels of this query; `judged_corpus` = documents judged for ANY query."""
    relevant = {d for d, g in grades.items() if g > 0}
    m: dict[str, float | None] = {}
    for k in cutoffs.get("ndcg", ()):
        m[f"nDCG@{k}"] = ndcg_at(ranking, grades, k)
    for k in cutoffs.get("map", ()):
        m[f"MAP@{k}"] = average_precision_at(ranking, relevant, k)
    for k in cutoffs.get("recall", ()):
        m[f"Recall@{k}"] = recall_at(ranking, relevant, k)
    for k in cutoffs.get("precision", ()):
        m[f"P@{k}"] = precision_at(ranking, relevant, k)
    for k in cutoffs.get("mrr", ()):
        m[f"MRR@{k}"] = reciprocal_rank_at(ranking, relevant, k)
    for k in cutoffs.get("hit", ()):
        m[f"HitRate@{k}"] = hit_at(ranking, relevant, k)
    for k in cutoffs.get("r_cap", ()):
        m[f"R_cap@{k}"] = capped_recall_at(ranking, relevant, k)
    for k in cutoffs.get("hole", ()):
        m[f"Hole@{k}"] = hole_at(ranking, judged_corpus, k)
    return m


def mean_metrics(per_query: list[dict[str, float | None]]) -> dict[str, dict]:
    """{metric: {"mean", "n" (queries with a defined value), "undefined" (queries excluded)}}."""
    names = sorted({name for q in per_query for name in q})
    result = {}
    for name in names:
        values = [q[name] for q in per_query if q.get(name) is not None]
        result[name] = {"mean": sum(values) / len(values) if values else None, "n": len(values), "undefined": len(per_query) - len(values)}
    return result


def evaluate_run(run: dict[str, list[str]], qrels: dict[str, dict[str, int]], cutoffs: dict = DEFAULT_CUTOFFS,
                 ignore_identical_ids: bool = True) -> tuple[dict[str, dict], dict[str, dict]]:
    """run {query_id: ranked doc IDs}, qrels {query_id: {doc_id: grade}} → (per-query metrics, averages).

    Queries without a ranking (e.g. a failed run) are scored as an EMPTY ranking — they are not dropped.
    """
    judged = {d for grades in qrels.values() for d in grades}
    per_query = {}
    for qid, grades in qrels.items():
        ranking = clean_ranking(run.get(qid, []), qid, ignore_identical_ids)
        per_query[qid] = query_metrics(ranking, grades, judged, cutoffs)
    return per_query, mean_metrics(list(per_query.values()))
