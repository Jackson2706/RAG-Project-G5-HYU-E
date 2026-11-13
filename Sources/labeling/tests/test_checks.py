"""Deterministic G4 label checks (labeling/checks.py, A33). Written by Claude Code."""

from labeling.checks import check_case

DOCS = {"s": {"text": "Seoul students apply for the TOPIK scholarship in March 2026.", "campus": "seoul", "post_date": "2026-02-01"},
        "e": {"text": "ERICA students apply for the TOPIK scholarship in April.", "campus": "erica", "post_date": None}}


def case(**kw):
    base = {"case_id": "x", "slice": "unconditional", "question": "When do I apply for the TOPIK scholarship?",
            "session_history": [], "stated_profile": {"campus": "seoul"}, "gold_profile": {"campus": "seoul", "visa": "D-2"},
            "branch_attributes": [], "answerability": "answerable", "expected_behavior": "answer",
            "required_facts": ["Seoul students apply for the TOPIK scholarship in March"], "condition_scope": "campus",
            "gold_evidence": [{"doc_id": "s", "char_start": 0, "char_end": 61, "applies_to_gold_profile": True}]}
    return {**base, **kw}


def checks(**kw):
    return [c for c, _ in check_case(case(**kw), DOCS)]


def test_a_clean_case_passes():
    assert check_case(case(), DOCS) == []


def test_behavior_must_follow_answerability():
    assert checks(answerability="external_only", expected_behavior="answer") == ["behavior"]
    assert checks(answerability="partial", expected_behavior="clarify", branch_attributes=["visa"]) == ["behavior"]
    assert checks(answerability="partial", expected_behavior="answer") == []


def test_branch_counts():
    marked = [{"doc_id": "s", "char_start": 0, "char_end": 61, "branch": {"visa": v}} for v in ("D-2", "D-4", "F-4")]
    assert "branches" in checks(expected_behavior="conditional_answer", branch_attributes=["visa"], gold_evidence=marked)
    assert "branches" in checks(expected_behavior="clarify", branch_attributes=["visa"], gold_evidence=marked[:2])
    assert "branches" in checks(expected_behavior="conditional_answer", branch_attributes=[])


def test_answer_with_an_unstated_branch_or_both_campuses():
    assert "unstated" in checks(branch_attributes=["visa"])
    both = [{"doc_id": d, "char_start": 0, "char_end": 40, "applies_to_gold_profile": True} for d in ("s", "e")]
    out = check_case(case(stated_profile={}, gold_evidence=both), DOCS)
    assert ("unstated", "answer with gold evidence from both campuses while campus is unstated") in out
    assert any(c == "campus" for c, _ in out)  # the ERICA span does not match the Seoul profile


def test_facts_profile_and_term():
    assert checks(required_facts=["Applicants submit a medical certificate"]) == ["facts"]
    assert checks(required_facts=["The deadline for ERICA is not described"]) == []  # an absence is skipped
    assert checks(stated_profile={"campus": "seoul", "visa": "D-4"}) == ["profile"]
    assert checks(question="When do I apply in 2027?") == ["term"]
    assert checks(question="When do I apply in 2026?") == []
    history = [{"role": "user", "text": "I am actually on a D-4 visa now."}]
    assert "profile" in checks(slice="multi_session", session_history=history)
    assert "profile" not in checks(slice="multi_session", session_history=history, stale_update=True)
