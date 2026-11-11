"""P6 baselines: R9-scope / R15 predicate, R15 LLM parsing, G0 and R16 prompts. Written by Claude Code."""

from __future__ import annotations

import pytest

from app.rag import aaes
from app.rag.blocks.grounded_generation.context_construction.closed_book import ClosedBookBuilder
from app.rag.blocks.grounded_generation.context_construction.conditional_prompt import ConditionalPromptBuilder
from app.rag.blocks.retrieval.lexical_retrieval.bm25 import app_payload
from app.rag.applicability import ChunkCondition
from app.rag.presets import PRESETS_BY_ID, preset_config, presets_json
from app.rag.schemas import RetrievalFilter


def test_scope_prefilter_drops_applicant_only_and_keeps_unconstrained_chunks():
    predicate = RetrievalFilter(conditions=aaes.prefilter_conditions(aaes.extract_profile("I'm at ERICA")), include_unknown=True)
    payload = lambda **kw: app_payload({"applicability": ChunkCondition(**kw).to_dict()})  # noqa: E731
    assert predicate.matches(payload(campus=["erica"]))
    assert not predicate.matches(payload(campus=["seoul"]))
    assert not predicate.matches(payload(campus=["erica"], constraints={"academic_status": ["applicant"]}))
    assert predicate.matches(payload(campus=["erica"], constraints={"academic_status": ["applicant", "enrolled"]}))
    alternatives = payload(campus=["erica"], any_of=[{"topik_level": ["3"]}, {"english_track": ["yes"]}])
    assert predicate.matches(alternatives)  # never dropped on its alternatives


def test_self_query_keeps_only_vocabulary_values():
    profile, dropped = aaes.profile_from_llm('Sure: {"campus": "erica", "visa": "D-9", "year": ["1", "2"], "gpa": "4.0"}')
    assert profile["campus"] == {"values": ["erica"], "status": "stated", "evidence": "llm"}
    assert profile["year"]["values"] == ["1", "2"] and profile["visa"]["status"] == "missing"
    assert sorted(dropped) == ["gpa=4.0", "visa=D-9"] and profile["academic_status"]["status"] == "scope_default"
    assert aaes.profile_from_llm("not json")[0]["campus"]["status"] == "missing"


@pytest.mark.anyio
async def test_closed_book_has_no_evidence_and_r16_adds_the_conditional_rule(services):
    closed = await ClosedBookBuilder({}, services).build("How do I register?", [])
    assert closed.evidence == [] and len(closed.messages) == 2 and "no documents" in closed.messages[0]["content"]
    services.embedder = type("E", (), {"count_tokens": lambda self, t: 0})()
    r16 = await ConditionalPromptBuilder({}, services).build("Can I work?", [])
    assert "If you are" in r16.messages[0]["content"]


def test_p6_presets_validate_and_g1_is_disabled_with_a_reason():
    for preset_id in ("G0_CLOSED_BOOK", "R9S_SCOPE_PREFILTER", "R15_SELF_QUERY", "R16_PROMPTED_CONDITIONAL"):
        assert preset_config(preset_id) and PRESETS_BY_ID[preset_id]["group"]
    assert PRESETS_BY_ID["G1_ORACLE_CONTEXT"]["enabled"] is False and "runner" in PRESETS_BY_ID["G1_ORACLE_CONTEXT"]["description"]
    g1 = next(p for p in presets_json() if p["id"] == "G1_ORACLE_CONTEXT")
    assert g1["config"] is None and g1["errors"][0]["message"] == "needs a labeled demo case"
