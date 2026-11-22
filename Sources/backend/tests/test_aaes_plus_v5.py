"""T42: current-turn identity and semantic branch grouping in AAES+ both mode."""

import asyncio
import doctest
import json

import pytest

from app.rag import aaes_llm
from app.rag.aaes import extract_profile
from app.rag.blocks.evidence.evidence_sufficiency.applicability_sufficiency import ApplicabilitySufficiency
from app.rag.blocks.query_processing.query_understanding.profile_understanding import ProfileUnderstanding
from app.rag.schemas import Evidence

PROBE = "If I were a master's student at ERICA, could I take the TOPIK class?"


def fake_llm(monkeypatch, *replies):
    pending, calls = list(replies), []

    async def reply(_block, system, user):
        assert pending, "Unexpected LLM call"
        calls.append((system, user))
        return pending.pop(0)

    monkeypatch.setattr(aaes_llm, "call", reply)
    return calls


@pytest.mark.parametrize("cue", ["If I were", "If I was", "Suppose", "Imagine", "What if", "Hypothetically", "Let's say"])
def test_rule_kind_hypothetical_cues_override_self_statements(cue):
    assert aaes_llm.rule_kind(f"{cue} I'm a master's student at ERICA.", "ERICA") == "hypothetical"


@pytest.mark.parametrize("text,quote,kind", [
    ("I'm a Seoul campus student.", "Seoul", "self"),
    ("I am at ERICA.", "ERICA", "self"),
    ("I study at ERICA.", "ERICA", "self"),
    ("My campus is ERICA.", "ERICA", "self"),
    ("I'm an exchange student.", "exchange student", "self"),
    ("I'm currently enrolled.", "I'm currently enrolled", "self"),
    ("I'm in Seoul. What about ERICA students?", "ERICA", "mention"),
    ("If I were in Seoul. I'm at ERICA.", "ERICA", "self"),
    ("What about ERICA students?", "ERICA", "mention"),
    ("ERICA", "ERICA", "mention"),
    ("I’m at  ERICA.", "ERICA", "self"),
    ("I'm at ERICA. Does ERICA offer winter school?", "ERICA", "self"),
    ("I'm a master's student. If I were a master's student at ERICA?", "master's", "hypothetical"),
    ("I'm at Seoul.", "ERICA", "mention"),
    ("I'm at Seoul.", "", "mention"),
])
def test_rule_kind_uses_the_quote_sentence(text, quote, kind):
    assert aaes_llm.rule_kind(text, quote) == kind


@pytest.mark.parametrize("raw", ["{}", "not json"])
def test_both_drops_unconfirmed_hypothetical_identity_even_on_parse_failure(monkeypatch, raw):
    fake_llm(monkeypatch, raw)
    block = ProfileUnderstanding({"mode": "both"}, services=None)
    profile = asyncio.run(block.analyze(PROBE)).profile
    assert profile["campus"]["status"] == profile["degree_level"]["status"] == "missing"
    assert profile["campus"]["values"] == profile["degree_level"]["values"] == []
    assert block.trace_details["dropped_unconfirmed"] == [
        {"attribute": "campus", "value": "erica", "kind": "hypothetical"},
        {"attribute": "degree_level", "value": "master", "kind": "hypothetical"},
    ]


@pytest.mark.parametrize("entries", [
    {"campus": {"value": "erica", "quote": "ERICA", "turn": "now"},
     "degree_level": {"value": "master", "quote": "master's", "turn": "now"}},
    {"campus": {"value": "seoul", "quote": "ERICA", "turn": "now"}},
    {"campus": {"value": "erica", "quote": "invented quote", "turn": "now"}},
])
def test_both_requires_matching_valid_llm_confirmation(monkeypatch, entries):
    fake_llm(monkeypatch, json.dumps(entries))
    block = ProfileUnderstanding({"mode": "both"}, services=None)
    profile = asyncio.run(block.analyze(PROBE)).profile
    confirmed = "degree_level" in entries
    assert profile["campus"]["values"] == (["erica"] if confirmed else [])
    assert profile["degree_level"]["values"] == (["master"] if confirmed else [])
    assert len(block.trace_details["dropped_unconfirmed"]) == (0 if confirmed else 2)


@pytest.mark.parametrize("raw,expected", [
    ("{}", []),
    ('{"campus": {"value": "erica", "quote": "ERICA", "turn": "now"}}', ["erica"]),
])
def test_both_bare_campus_requires_confirmation(monkeypatch, raw, expected):
    fake_llm(monkeypatch, raw)
    block = ProfileUnderstanding({"mode": "both"}, services=None)
    profile = asyncio.run(block.analyze("What about ERICA students?")).profile
    assert profile["campus"]["values"] == expected
    assert block.trace_details["dropped_unconfirmed"] == ([] if expected else [
        {"attribute": "campus", "value": "erica", "kind": "mention"}])


def test_both_self_and_remembered_rules_still_win(monkeypatch):
    fake_llm(monkeypatch, '{"campus": {"value": "erica", "quote": "ERICA", "turn": "earlier"}}')
    block = ProfileUnderstanding({"mode": "both"}, services=None)
    question, history = "I'm a Seoul campus student.", ["ERICA master's exchange student"]
    assert asyncio.run(block.analyze(question, history)).profile == extract_profile(question, history)
    assert block.trace_details["dropped_unconfirmed"] == []


def test_both_applies_scope_defaults_after_dropping_a_mention(monkeypatch):
    fake_llm(monkeypatch, "{}")
    block = ProfileUnderstanding({"mode": "both"}, services=None)
    entry = asyncio.run(block.analyze("What about admission requirements?")).profile["academic_status"]
    assert entry["status"] == "scope_default" and "applicant" not in entry["values"]


@pytest.mark.parametrize("mode,raw", [("rules", None), ("llm", "not json")])
def test_existing_profile_fallback_in_other_modes_is_unchanged(monkeypatch, mode, raw):
    calls = fake_llm(monkeypatch, *([] if raw is None else [raw]))
    block = ProfileUnderstanding({"mode": mode}, services=None)
    assert asyncio.run(block.analyze(PROBE)).profile == extract_profile(PROBE)
    assert len(calls) == (mode == "llm")
    assert "dropped_unconfirmed" not in block.trace_details


def branch_evidence():
    return [Evidence(rank=i, chunk_id=campus, doc_id=campus, score=1.0, text=f"{campus} winter school is available.",
                     title="Winter school", source_uri="synthetic", applicability={
                         "condition": {"campus": [campus], "scope": "campus", "constraints": {}},
                         "condition_status": "rule_tagged"})
            for i, campus in enumerate(("seoul", "erica"), 1)]


def sufficiency(step3="both"):
    return ApplicabilitySufficiency({"step3_mode": step3, "step4_mode": "rules", "relevance_threshold": 0.0,
                                    "max_branches": 3, "temporal": True, "policy": "aaes"}, services=None)


@pytest.mark.parametrize("same", [True, False])
def test_same_checks_one_answer_per_lexical_group(monkeypatch, same):
    calls = fake_llm(monkeypatch, "Yes, winter school is available.", "Students may enroll in winter courses.",
                     json.dumps({"same": same, "difference": "" if same else "Enrollment differs."}))
    block = sufficiency()
    result = asyncio.run(block.check("Can I attend winter school?", branch_evidence()))
    assert result.action == ("ANSWER" if same else "CLARIFY")
    assert result.signals["reason"] == ("same_meaning" if same else "different_procedures")
    assert result.signals["clarify_attribute"] == (None if same else "campus")
    assert result.signals["branch_attributes"] == ([] if same else ["campus"])
    assert [system for system, _ in calls] == [aaes_llm.EXTRACT, aaes_llm.EXTRACT, aaes_llm.SAME]
    assert "Can I attend winter school?" in calls[-1][1]
    assert calls[-1][1].count("Yes, winter school is available.") == 1
    assert calls[-1][1].count("Students may enroll in winter courses.") == 1
    assert block.trace_details["same_check"] == {"groups": 2, "same": same,
                                                 "difference": "" if same else "Enrollment differs."}


@pytest.mark.parametrize("answers,action,skip", [
    (("20 hours per week", "30 hours per week"), "CLARIFY", "different_numbers"),
    (("Fee: 30,000 won", "Fee: 40,000 won"), "CLARIFY", "different_numbers"),
    (("Yes, winter school is available.", "NONE"), "CLARIFY", "unanswered_set"),
    (("Yes, winter school is available.", "Yes, winter school is available."), "ANSWER", "same_answer"),
])
def test_same_is_skipped_for_numbers_none_and_lexical_agreement(monkeypatch, answers, action, skip):
    calls = fake_llm(monkeypatch, *answers)
    block = sufficiency()
    result = asyncio.run(block.check("Can I attend winter school?", branch_evidence()))
    assert result.action == action
    assert len(calls) == 2 and all(system == aaes_llm.EXTRACT for system, _ in calls)
    assert block.trace_details["same_check"] == f"skipped: {skip}"


@pytest.mark.parametrize("raw", ["not json", '{"same": "true", "difference": ""}', '{"same": true}',
                                  '{"same": true, "difference": 1}',
                                  json.dumps({"same": True, "difference": "word " * 16})])
def test_invalid_same_keeps_the_split_and_counts_a_fallback(monkeypatch, raw):
    fake_llm(monkeypatch, "Yes, winter school is available.", "Students may enroll in winter courses.", raw)
    block = sufficiency()
    result = asyncio.run(block.check("Can I attend winter school?", branch_evidence()))
    assert result.action == "CLARIFY" and result.signals["clarify_attribute"] == "campus"
    assert block.trace_details["fallbacks"]["same"] == 1
    assert block.trace_details["same_check"] == "skipped: invalid"


@pytest.mark.parametrize("mode", ["rules", "llm"])
def test_other_branch_modes_never_call_same(monkeypatch, mode):
    calls = fake_llm(monkeypatch, *(['{"differs": false}'] if mode == "llm" else []))
    block = sufficiency(mode)
    result = asyncio.run(block.check("Can I attend winter school?", branch_evidence()))
    assert result.action == ("ANSWER" if mode == "llm" else "CLARIFY")
    assert all(system == aaes_llm.DIFFERS for system, _ in calls)
    assert "same_check" not in block.trace_details


def test_same_gets_one_representative_for_repeated_groups_with_matching_numbers(monkeypatch):
    calls = fake_llm(monkeypatch, "Fee: 30,000 won", "30,000 won fee", "Pay 30000 KRW",
                     '{"same": true, "difference": ""}')
    items = branch_evidence()
    items.append(items[0].model_copy(update={"chunk_id": "third"}))
    decision = {"action": "CLARIFY", "branch_attributes": ["campus"], "clarify_attribute": "campus",
                "branch_table": [{"evidence": [item.chunk_id]} for item in items]}
    block = sufficiency()
    result = asyncio.run(block._extract_branches("What is the fee?", items, decision))
    assert result["reason"] == "same_meaning"
    assert len(calls) == 4 and calls[-1][0] == aaes_llm.SAME
    assert "Fee: 30,000 won" in calls[-1][1] and "Pay 30000 KRW" in calls[-1][1]
    assert "30,000 won fee" not in calls[-1][1]
    assert block.trace_details["same_check"]["groups"] == 2


def test_aaes_llm_doctests():
    assert doctest.testmod(aaes_llm).failed == 0
