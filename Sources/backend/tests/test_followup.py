"""Deck v6 follow-up resolution: detail-only replies to an AAES question answer the earlier question. Written by Claude Code."""

from __future__ import annotations

import pytest

from app.rag.followup import resolve
from app.rag.presets import PRESETS_BY_ID
from tests.test_aaes_pipeline import _tag_everything, api  # noqa: F401  (fixture)

Q = "How do I book the international student counseling program?"
CAMPUS = {"question": Q, "attribute": "campus", "options": ["seoul", "erica"]}
DEGREE = {"question": Q, "attribute": "degree_level", "options": ["undergraduate", "master", "doctoral"]}


@pytest.mark.parametrize("reply, marker, stated", [
    ("I'm a Seoul campus student.", CAMPUS, {"campus": "seoul"}),
    ("Seoul", CAMPUS, {"campus": "seoul"}),
    ("ERICA campus", CAMPUS, {"campus": "erica"}),
    ("ansan", CAMPUS, {"campus": "erica"}),
    ("I'm a master's student", DEGREE, {"degree_level": "master"}),
    ("grad", {**DEGREE, "options": ["undergraduate", "master"]}, {"degree_level": "master"}),
])  # fmt: skip
def test_detail_only_replies_answer_the_earlier_question(reply, marker, stated):
    assert resolve(reply, marker) == {"question": Q, "reply": reply, "stated": stated}


@pytest.mark.parametrize("reply, marker", [
    ("I'm a Seoul student, where is the dorm?", CAMPUS),
    ("Is ERICA different?", CAMPUS),
    ("Which scholarships can I get at Seoul", CAMPUS),  # starts with a question word
    ("I'm a Seoul campus student.", None),  # a new message after a normal answer: no clarify marker
    ("grad", DEGREE),  # graduate is not unique (master or doctoral)
    ("Thanks, that helps a lot", CAMPUS),  # no detail
    ("I'm at Seoul " + "really " * 20, CAMPUS),  # more than 20 words
    ("Tell me about dormitory fees at Seoul", CAMPUS),  # a new request that names a campus
])  # fmt: skip
def test_other_messages_are_unchanged(reply, marker):
    assert resolve(reply, marker) is None


def test_earlier_resolved_details_are_carried_forward():
    marker = {**DEGREE, "stated": {"campus": "seoul", "visa": "not-a-visa"}}  # an invalid carried value is dropped
    assert resolve("master", marker)["stated"] == {"campus": "seoul", "degree_level": "master"}


def test_reply_answers_the_earlier_question_end_to_end(api, corpus, db, fake_ollama, settings):  # noqa: F811
    api.post("/api/ingest", json={"folder": "raw"})
    _tag_everything(db, "seoul", "unconditioned")
    stages = PRESETS_BY_ID["A4_QUESTION_ONLY_AMBIGUITY"]["stages"]
    first = "I'm a Seoul campus student. Which scholarship documents do I need for my visa?"
    asked = api.post("/api/chat", json={"question": first, "stages": stages}).json()
    assert asked["action"] == "CLARIFY" and asked["clarify"]["question"] == first and asked["clarify"]["attribute"] == "visa"
    reply = {"question": "My visa is D-2.", "history": [first], "stages": stages, "followup": asked["clarify"]}
    trace = api.post("/api/chat", json=reply).json()
    assert trace["question"] == first and trace["followup"] == {"message": "My visa is D-2.", "answering": first, "stated": {"visa": "D-2"}}
    assert trace["action"] != "CLARIFY" or trace["clarify"]["attribute"] != "visa"  # the detail is not asked again
    profile = {s["stage_id"]: s for s in trace["stages"]}["query_understanding"]["output"]["profile"]
    assert profile["visa"] == {"values": ["D-2"], "status": "stated", "evidence": "My visa is D-2."}  # the traced profile is the one used
    settings.followup_resolution = False  # flag off: the reply is a new question, as before
    off = api.post("/api/chat", json=reply).json()
    assert off["question"] == "My visa is D-2." and off["followup"] is None
