"""Query-term coverage, exactly as in the Lesson 5 lab (L05_improve_retrieval.py, "query-term-coverage-v1").

Used by the coverage reranker and by the evidence sufficiency gate, so both use one definition.
"""

from __future__ import annotations

import re

TOKEN_PATTERN = re.compile(r"\w+(?:[-']\w+)*|[^\w\s]", re.UNICODE)
STOPWORDS = frozenset({
    "a", "an", "and", "are", "at", "before", "do", "does", "for", "from", "how", "i", "in", "is", "it",
    "many", "of", "on", "the", "to", "what", "where", "which", "with",
})  # fmt: skip


def content_terms(text: str) -> set[str]:
    """Unique lowercase words of a text, without punctuation and Lesson 5's stop words."""
    return {m.group(0).lower() for m in TOKEN_PATTERN.finditer(text) if m.group(0).isalnum() and m.group(0).lower() not in STOPWORDS}


def query_coverage(query: str, text: str) -> float:
    """Fraction of the query's unique content terms that also occur in the text (0.0 – 1.0).

    A lexical overlap signal only: high coverage does NOT prove that the text answers the query.
    """
    terms = content_terms(query)
    if not terms:
        return 0.0
    return len(terms & content_terms(text)) / len(terms)
