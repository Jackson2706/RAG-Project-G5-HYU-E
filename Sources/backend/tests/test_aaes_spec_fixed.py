"""A0b helpers (amendment A34). Written by Claude Code."""

from app.rag.aaes import answer_key, both_campuses_scoped, decide, distinct_answers, extract_profile


def test_campus_candidate_needs_both_campuses_scoped():
    seoul, erica, national = ({"condition": {"campus": c}} for c in (["seoul"], ["erica"], ["seoul", "erica"]))
    assert both_campuses_scoped([seoul, erica, national])
    assert not both_campuses_scoped([seoul, national])
    assert not both_campuses_scoped([])


def test_answer_values_group_by_word_overlap():
    keys = [answer_key("30,000 won"), answer_key("The fee is 30,000 won."), answer_key("Free of charge"), answer_key("NONE"), answer_key("")]
    assert keys[3] is None and keys[4] is None
    assert distinct_answers(keys) == [0, 0, 1, -1, -1]


def test_exclude_removes_an_attribute_from_the_branches():
    chunks = [{"id": "s", "doc_id": "D1", "condition": {"campus": ["seoul"]}, "status": "unconditioned"},
              {"id": "e", "doc_id": "D2", "condition": {"campus": ["erica"]}, "status": "unconditioned"}]  # fmt: skip
    profile = extract_profile("How much is the dormitory fee?")
    assert decide(chunks, profile)["action"] == "CLARIFY"  # A0: two documents -> different_procedures
    assert decide(chunks, profile, exclude=frozenset({"campus"}))["action"] == "ANSWER"


def test_yes_no_and_negation_are_different_answers():
    assert distinct_answers([answer_key("Yes"), answer_key("No")]) == [0, 1]
    assert distinct_answers([answer_key("Required"), answer_key("Not required")]) == [0, 1]
    assert answer_key("None required") is not None and answer_key("NONE.") is None
