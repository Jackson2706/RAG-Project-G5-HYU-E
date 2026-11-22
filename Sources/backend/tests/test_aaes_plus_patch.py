"""Regression tests for the AAES+ Step 2 fallbacks and Step 3 numeric comparison."""

import asyncio

from app.rag import aaes_llm
from app.rag.aaes import extract_profile
from app.rag.blocks.evidence.reranking.applicability_reranker import ApplicabilityReranker
from app.rag.blocks.evidence.reranking.cross_encoder import CrossEncoderReranker
from app.rag.schemas import Evidence


def evidence(chunk_id: str, text: str, campus: list[str]) -> Evidence:
    condition = {"campus": campus, "scope": "campus", "constraints": {}, "any_of": []}
    return Evidence(rank=1, chunk_id=chunk_id, doc_id="d", score=1.0, text=text, title="t", source_uri="u",
                    applicability={"condition": condition, "condition_status": "rule_tagged"})  # fmt: skip


def test_invalid_or_missing_applicability_items_fall_back_to_rules(monkeypatch):
    items = [evidence("seoul", "Only Seoul campus students may apply.", ["seoul"]),
             evidence("erica", "Only ERICA campus students may apply.", ["erica"])]  # fmt: skip

    async def ranked(_self, _query, evidence, _profile=None):
        return evidence

    async def reply(_block, _system, _user):
        return ('{"passages": [{"id": "P1", "relevant": true, "applies": "other_students", '
                '"depends_on": [], "quote": "not in the passage"}]}')

    monkeypatch.setattr(CrossEncoderReranker, "rerank", ranked)
    monkeypatch.setattr(aaes_llm, "call", reply)
    block = ApplicabilityReranker({"rerank_depth": 2, "llm_depth": 6, "mode": "both", "hard_filter": False,
                                   "lam": 1.0, "mu": 0.0}, services=None)  # type: ignore[arg-type]
    result = asyncio.run(block.rerank("Who may apply?", items, extract_profile("I'm a Seoul campus student.")))

    by_id = {item.chunk_id: item for item in result}
    assert by_id["seoul"].applicability["label"] == "unconditioned"
    assert by_id["erica"].applicability["label"] == "conflicting"
    assert block.trace_details["fallbacks"]["applies"] == 2  # invalid P1 and missing P2


def test_hybrid_gets_llm_relevance_for_tagged_passages_but_keeps_rule_labels(monkeypatch):
    items = [evidence("seoul", "Seoul insurance costs 20,000 won.", ["seoul"]),
             evidence("erica", "ERICA insurance costs 30,000 won.", ["erica"])]  # fmt: skip

    async def ranked(_self, _query, evidence, _profile=None):
        return evidence

    async def reply(_block, _system, user):
        assert "[P1]" in user and "[P2]" in user
        return ('{"passages": [{"id": "P1", "relevant": true, "applies": "everyone", "depends_on": [], "quote": ""}, '
                '{"id": "P2", "relevant": true, "applies": "everyone", "depends_on": [], "quote": ""}]}')

    monkeypatch.setattr(CrossEncoderReranker, "rerank", ranked)
    monkeypatch.setattr(aaes_llm, "call", reply)
    block = ApplicabilityReranker({"rerank_depth": 2, "llm_depth": 6, "mode": "both", "hard_filter": False,
                                   "lam": 1.0, "mu": 0.0}, services=None)  # type: ignore[arg-type]
    result = asyncio.run(block.rerank("How much is insurance?", items, extract_profile("I'm a Seoul campus student.")))

    by_id = {item.chunk_id: item for item in result}
    assert by_id["seoul"].applicability["label"] == "unconditioned"
    assert by_id["erica"].applicability["label"] == "conflicting"
    assert all(item.applicability["llm_relevant"] is True for item in result)


def test_numeric_contradictions_are_not_collapsed_by_overlap():
    raw = ('{"differs": true, "detail": "campus", "answers": '
           '{"seoul": "20 hours per week", "erica": "30 hours per week"}}')
    assert aaes_llm.parse_differs(raw, {})["differs"] is True
