"""Abstract class for Query Rewriting."""

from __future__ import annotations

import re
from abc import abstractmethod

from app.rag.blocks.pipeline_block import PipelineBlock
from app.rag.schemas import RewrittenQuery

NEGATIONS = {"not", "no", "never", "without", "except", "cannot", "can't", "don't", "doesn't", "isn't", "aren't", "won't", "nor"}
PREFIX = re.compile(r"^\s*(?:\d+[.)]|[-*•]|(?:rewritten |search )?query\s*:)\s*", re.IGNORECASE)


def required_terms(question: str) -> list[str]:
    """What a rewrite must keep: numbers, quoted phrases, and names (words with a capital letter that do
    not start a sentence, or ALL-CAPS words such as ERICA)."""
    terms = re.findall(r"\d+(?:[.,:/-]\d+)*", question) + re.findall(r'"([^"]+)"', question)
    words = re.findall(r"[A-Za-z][\w'-]*", question)
    for i, word in enumerate(words):
        sentence_start = i == 0 or re.search(re.escape(words[i - 1]) + r"[.?!]\s+" + re.escape(word), question)
        if (word.isupper() and len(word) > 1) or (word[0].isupper() and not sentence_start):
            terms.append(word)
    return list(dict.fromkeys(terms))


def clean_query(text: str) -> str:
    """Remove list numbering, "Query:" prefixes and surrounding quotes from one LLM output line."""
    return PREFIX.sub("", text.strip()).strip().strip('"').strip()


def validate_rewrite(question: str, rewritten: str) -> dict:
    """Check that a rewrite is still the SAME information need. Returns {passed, missing, reason}.

    Fails when the rewrite is empty or very long, drops a required term (number, quoted phrase, name),
    or drops the negation of a negated question. A failed rewrite is never used: the caller falls
    back to the original question.
    """
    lowered = rewritten.lower()
    missing = [t for t in required_terms(question) if t.lower() not in lowered]
    words = re.findall(r"[\w']+", question.lower())
    if any(w in NEGATIONS for w in words) and not any(w in NEGATIONS for w in re.findall(r"[\w']+", lowered)):
        missing.append("(negation)")
    if not rewritten.strip():
        return {"passed": False, "missing": missing, "reason": "empty rewrite"}
    if len(rewritten.split()) > max(3 * len(question.split()), 32):
        return {"passed": False, "missing": missing, "reason": "rewrite is much longer than the question"}
    if missing:
        return {"passed": False, "missing": missing, "reason": "required terms were dropped: " + ", ".join(missing)}
    return {"passed": True, "missing": [], "reason": "all required terms kept"}


class BaseQueryRewriter(PipelineBlock):
    """Input: the question. Output: RewrittenQuery (the search query + optional alternatives).

    The ORIGINAL question is still used in the prompt; only retrieval uses the rewritten query.
    """

    @abstractmethod
    async def rewrite(self, question: str) -> RewrittenQuery: ...
