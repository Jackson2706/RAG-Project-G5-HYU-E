"""AAES+ (deck v4 Task 4): validation of every LLM output; invalid items fall back to the rules."""

from app.rag import aaes_llm
from app.rag.aaes import decide, extract_profile


def test_profile_quote_must_appear_in_the_claimed_turn():
    raw = ('{"campus": {"value": "erica", "quote": "at ERICA", "turn": "now"}, '
           '"degree_level": {"value": "master", "quote": "grad student", "turn": "earlier"}, '
           '"visa": {"value": "D-99", "quote": "D-2", "turn": "now"}}')
    found, rejected = aaes_llm.parse_profile(raw, "I’m at  ERICA. Can I work?", ["I'm a grad student"])
    assert found == {"campus": ("erica", "stated", "at ERICA"), "degree_level": ("master", "remembered", "grad student")}
    assert rejected == ["visa:value"]
    assert aaes_llm.parse_profile("not json", "q", [])[1] == ["unparseable"]
    assert aaes_llm.parse_profile('{"campus": {"value": "seoul", "quote": "Seoul", "turn": "now"}}', "What about ERICA?", [])[1] == ["campus:quote"]


def test_conflict_needs_a_verified_quote_naming_a_known_attribute():
    passages = {"P1": "Only ERICA campus students may apply.", "P2": "All students pay 25,000 won."}
    raw = ('{"passages": [{"id": "P1", "relevant": true, "applies": "other_students", "quote": "Only ERICA campus students"}, '
           '{"id": "P2", "relevant": true, "applies": "other_students", "quote": "pay 25,000 won"}, {"id": "P9", "relevant": true, "applies": "everyone"}]}')
    out, rejected = aaes_llm.parse_applies(raw, passages, {"campus": ["seoul"]})
    assert out["P1"]["label"] == "conflicting" and out["P2"]["label"] == "open"  # no known attribute named -> depends
    assert "P9:shape" in rejected and "P2:conflict_quote" in rejected


def test_differs_needs_an_unknown_vocabulary_detail_and_two_distinct_answers():
    ok = '{"differs": true, "detail": "campus", "answers": {"seoul": "20 hours per week", "erica": "30 hours on weekdays"}}'
    assert aaes_llm.parse_differs(ok, {})["answers"]["erica"] == "30 hours on weekdays"
    assert aaes_llm.parse_differs(ok, {"campus": ["seoul"]}) is None  # already known
    assert aaes_llm.parse_differs('{"differs": true, "detail": "gpa", "answers": {"a": "x", "b": "y"}}', {}) is None
    assert aaes_llm.parse_differs('{"differs": true, "detail": "campus", "answers": {"seoul": "25,000 won fee", "erica": "fee 25,000 won"}}', {}) is None
    assert aaes_llm.parse_differs('{"differs": false}', {}) == {"differs": False, "detail": None, "answers": {}}


def test_decide_and_wording_checks():
    assert aaes_llm.parse_decide('{"action": "ask", "detail": "campus"}', {})["action"] == "CLARIFY"
    assert aaes_llm.parse_decide('{"action": "ask", "detail": "campus"}', {"campus": ["erica"]}) is None
    assert aaes_llm.parse_decide('{"action": "maybe"}', {}) is None
    assert aaes_llm.check_wording("Are you at Seoul or ERICA? The fees differ.", "ask", ["seoul", "erica"], None) is None  # must end with ?
    assert aaes_llm.check_wording("The fees differ: are you at the Seoul or the ERICA campus?", "ask", ["seoul", "erica"], None)
    assert aaes_llm.check_wording("Please contact the ERICA OIA office.", "refer", [], "seoul") is None
    assert aaes_llm.check_wording("Please contact the Seoul campus OIA office.", "refer", [], "seoul")


def test_fixed_llm_labels_change_what_applies():
    profile = extract_profile("Can I work part time?")
    seoul = {"id": "a", "doc_id": "d1", "condition": {"campus": ["seoul"], "scope": "campus", "constraints": {}}, "status": "conditioned"}
    erica = {"id": "b", "doc_id": "d1", "condition": {"campus": ["erica"], "scope": "campus", "constraints": {}}, "status": "conditioned"}
    assert decide([seoul, erica], profile)["branch_attributes"] == ["campus"]
    both_apply = [{**seoul, "fixed_label": "unconditioned"}, {**erica, "fixed_label": "unconditioned"}]
    assert decide(both_apply, profile)["action"] == "ANSWER"
    assert decide([{**seoul, "fixed_label": "conflicting"}], profile)["action"] == "ABSTAIN"
