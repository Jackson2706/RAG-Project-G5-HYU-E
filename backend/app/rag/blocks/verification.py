"""Blocks after generation: check citations, then decide the final answer.

    Citation Verification   BaseCitationVerifier → MarkerCitationVerifier (IMPLEMENTED), ClaimVerifier (PLANNED)
    Response Guard          BaseResponseGuard    → BasicResponseGuard (IMPLEMENTED)
"""

from __future__ import annotations

import re
from abc import abstractmethod

from app.rag.blocks.base import PipelineBlock
from app.rag.blocks.generation import INSUFFICIENT_MARKER
from app.rag.schemas import Citation, CitationResult, Evidence, FinalAnswer

INSUFFICIENT_ANSWER = (
    "I could not find enough information in the indexed HYU documents to answer this question. "
    "Please check the official Hanyang University website or ask the relevant office."
)


class BaseCitationVerifier(PipelineBlock):
    """Check the citations in an answer.

    Input:  the answer text and the labelled Evidence that was in the prompt
    Output: CitationResult (answer without invalid markers, citations, invalid markers)
    """

    @abstractmethod
    async def verify(self, answer: str, evidence: list[Evidence]) -> CitationResult: ...


class MarkerCitationVerifier(BaseCitationVerifier):
    """IMPLEMENTED — link [E1]-style markers to the real chunks; remove markers that match no evidence.

    This proves a citation points to real evidence. It does NOT prove the sentence is true.
    """

    async def verify(self, answer: str, evidence: list[Evidence]) -> CitationResult:
        labels = {e.label for e in evidence}
        found = list(dict.fromkeys(re.findall(r"\[(E\d+)\]", answer)))
        invalid = [m for m in found if m not in labels]
        for marker in invalid:
            answer = answer.replace(f"[{marker}]", "")
        citations = [
            Citation(label=e.label, cited=e.label in found, chunk_id=e.chunk_id, doc_id=e.doc_id, title=e.title,
                     source_uri=e.source_uri, section=e.section, page_number=e.page_number, score=e.score, excerpt=e.text[:500])
            for e in evidence
        ]  # fmt: skip
        return CitationResult(answer=answer, citations=citations, invalid_markers=invalid)


class ClaimVerifier(BaseCitationVerifier):
    """PLANNED — check that each sentence is supported by the evidence it cites."""

    async def verify(self, answer: str, evidence: list[Evidence]) -> CitationResult:
        # TODO:
        # 1. Split the answer into sentences and find each sentence's [E#] markers.
        # 2. Ask a model (e.g. an NLI model) whether the cited text supports the sentence.
        # 3. Remove or flag unsupported sentences.
        raise NotImplementedError("Claim verification is not implemented yet.")


class BaseResponseGuard(PipelineBlock):
    """Decide what the user finally sees.

    Input:  the verified CitationResult, or None when no answer was generated (no evidence)
    Output: FinalAnswer (answer, outcome, citations)
    """

    @abstractmethod
    async def finalize(self, result: CitationResult | None) -> FinalAnswer: ...


class BasicResponseGuard(BaseResponseGuard):
    """IMPLEMENTED — show a clear "not enough information" message when there was no evidence
    or the model answered INSUFFICIENT_CONTEXT; otherwise show the answer and its citations."""

    async def finalize(self, result: CitationResult | None) -> FinalAnswer:
        if result is None:
            return FinalAnswer(INSUFFICIENT_ANSWER, "insufficient_context", [])
        if result.answer.upper().startswith(INSUFFICIENT_MARKER):
            note = result.answer[len(INSUFFICIENT_MARKER):].strip(" :\n")
            return FinalAnswer(INSUFFICIENT_ANSWER + (f"\n\n_Model note: {note}_" if note else ""), "insufficient_context", [])
        return FinalAnswer(result.answer, "answered", result.citations)
